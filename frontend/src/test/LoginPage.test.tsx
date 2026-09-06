import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "../features/auth/LoginPage";
import { renderWithProviders } from "./utils";

const login = vi.fn();

vi.mock("../features/auth/AuthContext", async () => {
  const actual = await vi.importActual<object>("../features/auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({ user: null, ready: true, login, register: vi.fn(), logout: vi.fn() }),
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    login.mockReset();
  });

  it("renders the form", () => {
    renderWithProviders(<LoginPage />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("blocks submission and shows a message when the email is malformed", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "not-an-email");
    await user.type(screen.getByLabelText(/password/i), "correct-horse");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/does not look like an email/i)).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("requires a password", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "priya@example.com");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/password is required/i)).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("submits valid credentials", async () => {
    const user = userEvent.setup();
    login.mockResolvedValue(undefined);
    renderWithProviders(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "priya@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct-horse-battery");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(login).toHaveBeenCalledWith("priya@example.com", "correct-horse-battery"),
    );
  });

  it("surfaces a rejected login without clearing the form", async () => {
    const user = userEvent.setup();
    login.mockRejectedValue({
      isAxiosError: true,
      response: { status: 401, data: { message: "Incorrect email or password." } },
    });
    renderWithProviders(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), "priya@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toHaveValue("priya@example.com");
  });
});
