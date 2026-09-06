import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";
import type { Envelope, TokenResponse } from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * The access token lives in memory only. The refresh token is an httpOnly cookie
 * the browser sends on its own -- neither is ever written to localStorage, so an
 * XSS bug cannot walk off with a session.
 */
let accessToken: string | null = null;
let onSessionLost: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export function onUnauthenticated(handler: () => void) {
  onSessionLost = handler;
}

export const api: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  withCredentials: true, // required for the refresh cookie across origins
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

/** A failed request that triggers a refresh is retried exactly once. */
type Retriable = InternalAxiosRequestConfig & { _retried?: boolean };

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  // Collapse parallel 401s into a single refresh call.
  if (!refreshing) {
    refreshing = axios
      .post<Envelope<TokenResponse>>(
        `${BASE_URL}/api/v1/auth/refresh`,
        {},
        { withCredentials: true },
      )
      .then((response) => {
        const token = response.data.data?.access_token ?? null;
        setAccessToken(token);
        return token;
      })
      .catch(() => {
        setAccessToken(null);
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<Envelope<unknown>>) => {
    const original = error.config as Retriable | undefined;
    const isAuthCall = original?.url?.startsWith("/auth/");

    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      const token = await refreshAccessToken();
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
      onSessionLost?.();
    }
    return Promise.reject(error);
  },
);

/** Unwraps the API envelope so callers deal in plain data. */
export async function unwrap<T>(promise: Promise<{ data: Envelope<T> }>): Promise<T> {
  const response = await promise;
  return response.data.data as T;
}

export interface ApiError {
  message: string;
  code: string;
  status: number;
}

export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as Envelope<unknown> | undefined;
    return {
      message: body?.message ?? "Something went wrong. Please try again.",
      code: body?.error_code ?? "NETWORK_ERROR",
      status: error.response?.status ?? 0,
    };
  }
  return { message: "Something went wrong.", code: "UNKNOWN", status: 0 };
}

export { refreshAccessToken };
