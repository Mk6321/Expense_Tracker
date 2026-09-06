import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router-dom";
import ExpensesPage from "../features/expenses/ExpensesPage";
import { renderWithProviders } from "./utils";
import type { Expense, Group } from "../types/api";

const GROUP: Group = {
  id: 1,
  name: "Flat 3B",
  currency: "INR",
  created_by: 1,
  is_archived: false,
  created_at: "2026-01-01T00:00:00Z",
  role: "admin",
  member_count: 3,
  my_balance: "120.00",
};

function expense(overrides: Partial<Expense>): Expense {
  return {
    id: 1,
    group_id: 1,
    description: "Dinner",
    amount: "120.00",
    currency: "INR",
    paid_by: 1,
    paid_by_name: "Alice",
    category_id: null,
    category_name: "Food & Drink",
    expense_date: "2026-02-14",
    split_type: "equal",
    notes: null,
    created_by: 1,
    version: 1,
    is_reversed: false,
    reversed_by: null,
    reversed_at: null,
    created_at: "2026-02-14T00:00:00Z",
    updated_at: "2026-02-14T00:00:00Z",
    splits: [],
    my_share: "40.00",
    ...overrides,
  };
}

const EXPENSES = [
  expense({ id: 1, description: "Dinner", amount: "120.00", my_share: "40.00" }),
  expense({
    id: 2,
    description: "Cab home",
    amount: "300.50",
    paid_by: 2,
    paid_by_name: "Bob",
    category_name: "Transport",
    my_share: "100.17",
  }),
  expense({ id: 3, description: "Cancelled booking", amount: "999.00", is_reversed: true }),
];

const reverseExpense = vi.fn();

vi.mock("../features/auth/AuthContext", async () => {
  const actual = await vi.importActual<object>("../features/auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { id: 1, name: "Alice", email: "a@b.c", is_active: true, created_at: "" },
      ready: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    }),
  };
});

vi.mock("../lib/queries", async () => {
  const actual = await vi.importActual<object>("../lib/queries");
  return {
    ...actual,
    useGroup: () => ({ data: GROUP, isLoading: false }),
    useExpenses: () => ({
      data: { items: EXPENSES, next_cursor: null },
      isLoading: false,
    }),
    useMembers: () => ({ data: [], isLoading: false }),
    useCategories: () => ({ data: [], isLoading: false }),
    useReverseExpense: () => ({ mutateAsync: reverseExpense, isPending: false }),
    useCreateExpense: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateExpense: () => ({ mutateAsync: vi.fn(), isPending: false }),
  };
});

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/groups/:groupId/expenses" element={<ExpensesPage />} />
    </Routes>,
    { route: "/groups/1/expenses" },
  );
}

describe("ExpensesPage", () => {
  beforeEach(() => {
    reverseExpense.mockReset();
    reverseExpense.mockResolvedValue({});
  });

  it("lists non-reversed expenses with amounts, payer and share", () => {
    renderPage();

    expect(screen.getByText("Dinner")).toBeInTheDocument();
    expect(screen.getByText("₹120.00")).toBeInTheDocument();
    expect(screen.getByText("₹300.50")).toBeInTheDocument();
    expect(screen.getByText(/your share ₹40.00/i)).toBeInTheDocument();
    expect(screen.getByText(/Alice paid/)).toBeInTheDocument();
  });

  it("hides reversed expenses until they are asked for", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(screen.queryByText("Cancelled booking")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /show reversed/i }));
    expect(await screen.findByText("Cancelled booking")).toBeInTheDocument();
  });

  it("filters as you search", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/search expenses/i), "cab");

    await waitFor(() => expect(screen.queryByText("Dinner")).not.toBeInTheDocument());
    expect(screen.getByText("Cab home")).toBeInTheDocument();
  });

  it("says so when a search matches nothing", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/search expenses/i), "zzzzz");
    expect(await screen.findByText(/nothing matches that search/i)).toBeInTheDocument();
  });

  it("confirms before reversing, and explains that nothing is deleted", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /reverse Dinner/i }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/nothing is deleted/i);
    expect(reverseExpense).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /^reverse$/i }));
    await waitFor(() => expect(reverseExpense).toHaveBeenCalledWith(1));
  });

  it("can back out of the reversal dialog", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /reverse Dinner/i }));
    await user.click(await screen.findByRole("button", { name: /keep it/i }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(reverseExpense).not.toHaveBeenCalled();
  });
});
