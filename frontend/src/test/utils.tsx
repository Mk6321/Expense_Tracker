import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";
import { AuthProvider } from "../features/auth/AuthContext";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
}

/** Renders with router + query client but without the auth bootstrap. */
export function renderWithProviders(ui: ReactElement, { route = "/" } = {}) {
  const queryClient = makeQueryClient();
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

/** Adds the auth provider, for components that call useAuth(). */
export function renderWithAuth(ui: ReactElement, { route = "/" } = {}) {
  const queryClient = makeQueryClient();
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider>{ui}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}
