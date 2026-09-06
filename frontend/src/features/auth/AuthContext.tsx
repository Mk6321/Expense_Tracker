import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  api,
  onUnauthenticated,
  refreshAccessToken,
  setAccessToken,
  unwrap,
} from "../../lib/api";
import type { Envelope, TokenResponse, User } from "../../types/api";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const queryClient = useQueryClient();

  const clear = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    onUnauthenticated(clear);
  }, [clear]);

  // On boot the access token is gone (it only ever lived in memory), but the
  // refresh cookie may still be valid -- so try once before showing the login page.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await refreshAccessToken();
      if (cancelled) return;
      if (token) {
        try {
          const me = await unwrap<User>(api.get<Envelope<User>>("/auth/me"));
          if (!cancelled) setUser(me);
        } catch {
          if (!cancelled) clear();
        }
      }
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [clear]);

  const adopt = useCallback((token: TokenResponse) => {
    setAccessToken(token.access_token);
    setUser(token.user);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      ready,
      login: async (email, password) => {
        const token = await unwrap<TokenResponse>(
          api.post<Envelope<TokenResponse>>("/auth/login", { email, password }),
        );
        adopt(token);
      },
      register: async (name, email, password) => {
        const token = await unwrap<TokenResponse>(
          api.post<Envelope<TokenResponse>>("/auth/register", { name, email, password }),
        );
        adopt(token);
      },
      logout: async () => {
        try {
          await api.post("/auth/logout");
        } finally {
          clear();
        }
      },
    }),
    [user, ready, adopt, clear],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
