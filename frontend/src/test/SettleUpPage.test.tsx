import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router-dom";
import SettleUpPage from "../features/settlements/SettleUpPage";
import DashboardPage from "../features/groups/DashboardPage";
import { renderWithProviders } from "./utils";
import type { Group, Member, Settlement, Suggestions } from "../types/api";

const GROUP: Group = {
  id: 1,
  name: "Flat 3B",
  currency: "INR",
  created_by: 1,
  is_archived: false,
  created_at: "2026-01-01T00:00:00Z",
  role: "member",
  member_count: 3,
  my_balance: "-100.00",
};

const MEMBERS: Member[] = [
  { user_id: 1, name: "Alice", email: "a@x.c", role: "admin", status: "active", joined_at: "2026-01-01T00:00:00Z" },
  { user_id: 2, name: "Bob", email: "b@x.c", role: "member", status: "active", joined_at: "2026-01-01T00:00:00Z" },
  { user_id: 3, name: "Cara", email: "c@x.c", role: "member", status: "active", joined_at: "2026-01-01T00:00:00Z" },
];

// Bob (the signed-in user) owes Alice 100. Cara owes Alice 100 as well.
const SUGGESTIONS: Suggestions = {
  group_id: 1,
  currency: "INR",
  suggestions: [
    { from_user_id: 2, from_name: "Bob", to_user_id: 1, to_name: "Alice", amount: "100.00" },
    { from_user_id: 3, from_name: "Cara", to_user_id: 1, to_name: "Alice", amount: "100.00" },
  ],
  pairwise: [
    { from_user_id: 2, from_name: "Bob", to_user_id: 1, to_name: "Alice", amount: "60.00" },
    { from_user_id: 2, from_name: "Bob", to_user_id: 3, to_name: "Cara", amount: "40.00" },
  ],
  you_owe: "100.00",
  you_are_owed: "0.00",
};

const SETTLEMENTS: Settlement[] = [
  {
    id: 7,
    group_id: 1,
    from_user_id: 2,
    from_name: "Bob",
    to_user_id: 1,
    to_name: "Alice",
    amount: "25.00",
    settlement_date: "2026-02-10",
    notes: "UPI",
    created_by: 2,
    created_at: "2026-02-10T00:00:00Z",
    is_reversed: false,
    reversed_by: null,
    reversed_at: null,
  },
];

const createSettlement = vi.fn();
const reverseSettlement = vi.fn();

vi.mock("../features/auth/AuthContext", async () => {
  const actual = await vi.importActual<object>("../features/auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { id: 2, name: "Bob", email: "b@x.c", is_active: true, created_at: "" },
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
    useMembers: () => ({ data: MEMBERS, isLoading: false }),
    useCategories: () => ({ data: [], isLoading: false }),
    useSuggestions: () => ({ data: SUGGESTIONS, isLoading: false }),
    useSettlements: () => ({ data: { items: SETTLEMENTS, next_cursor: null }, isLoading: false }),
    useBalances: () => ({
      data: {
        group_id: 1,
        currency: "INR",
        balances: [
          { user_id: 1, name: "Alice", total_paid: "300.00", total_share: "100.00", settlements_paid: "0.00", settlements_received: "0.00", balance: "200.00" },
          { user_id: 2, name: "Bob", total_paid: "0.00", total_share: "100.00", settlements_paid: "0.00", settlements_received: "0.00", balance: "-100.00" },
          { user_id: 3, name: "Cara", total_paid: "0.00", total_share: "100.00", settlements_paid: "0.00", settlements_received: "0.00", balance: "-100.00" },
        ],
        pairwise: SUGGESTIONS.pairwise,
        my_balance: "-100.00",
        total_outstanding: "200.00",
      },
      isLoading: false,
    }),
    useExpenses: () => ({ data: { items: [], next_cursor: null }, isLoading: false }),
    useReports: () => ({
      data: {
        summary: {
          group_id: 1,
          currency: "INR",
          total_spend: "300.00",
          expense_count: 1,
          member_count: 3,
          my_total_paid: "0.00",
          my_total_share: "100.00",
          my_balance: "-100.00",
          average_expense: "300.00",
          largest_expense: "300.00",
          first_expense_date: "2026-02-01",
          last_expense_date: "2026-02-01",
        },
        categories: [],
        members: [],
        monthly: [],
      },
      isLoading: false,
    }),
    useCreateSettlement: () => ({ mutateAsync: createSettlement, isPending: false }),
    useReverseSettlement: () => ({ mutateAsync: reverseSettlement, isPending: false }),
  };
});

function renderSettle() {
  return renderWithProviders(
    <Routes>
      <Route path="/groups/:groupId/settle" element={<SettleUpPage />} />
    </Routes>,
    { route: "/groups/1/settle" },
  );
}

describe("SettleUpPage", () => {
  beforeEach(() => {
    createSettlement.mockReset();
    createSettlement.mockResolvedValue({ id: 9 });
    reverseSettlement.mockReset();
    reverseSettlement.mockResolvedValue({});
  });

  it("shows what you owe and what you are owed", () => {
    renderSettle();
    expect(screen.getByText("You owe")).toBeInTheDocument();
    expect(screen.getByText("You are owed")).toBeInTheDocument();
    expect(screen.getAllByText("₹100.00").length).toBeGreaterThan(0);
    expect(screen.getByText("₹0.00")).toBeInTheDocument();
  });

  it("offers the simplified plan and the unsimplified ledger side by side", async () => {
    const user = userEvent.setup();
    renderSettle();

    // Simplified: Bob -> Alice 100.
    expect(screen.getByText(/fewest transfers/i)).toBeInTheDocument();
    expect(screen.getAllByText("₹100.00").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /who paid what/i }));

    expect(await screen.findByText(/unsimplified/i)).toBeInTheDocument();
    expect(screen.getByText("₹60.00")).toBeInTheDocument();
    expect(screen.getByText("₹40.00")).toBeInTheDocument();
  });

  it("records a payment prefilled from the plan", async () => {
    const user = userEvent.setup();
    renderSettle();

    await user.click(screen.getAllByRole("button", { name: /mark paid/i })[0]);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText(/^from$/i)).toHaveValue("2");
    expect(within(dialog).getByLabelText(/^to$/i)).toHaveValue("1");
    expect(within(dialog).getByLabelText(/^amount$/i)).toHaveValue("100.00");

    await user.click(within(dialog).getByRole("button", { name: /record ₹100.00/i }));

    await waitFor(() => expect(createSettlement).toHaveBeenCalledTimes(1));
    expect(createSettlement.mock.calls[0][0]).toMatchObject({
      from_user_id: 2,
      to_user_id: 1,
      amount: "100.00",
    });
  });

  it("blocks a settlement between the same person twice", async () => {
    const user = userEvent.setup();
    renderSettle();

    await user.click(screen.getByRole("button", { name: /record a payment/i }));
    const dialog = await screen.findByRole("dialog");

    // "To" excludes whoever is selected as "from", so a self-payment is unreachable.
    const to = within(dialog).getByLabelText(/^to$/i);
    expect(within(to).queryByRole("option", { name: /Bob/ })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /record payment/i })).toBeDisabled();
  });

  it("lists settlement history and can reverse one", async () => {
    const user = userEvent.setup();
    renderSettle();

    expect(screen.getByText("₹25.00")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /reverse settlement/i }));
    await waitFor(() => expect(reverseSettlement).toHaveBeenCalledWith(7));
  });
});

describe("Dashboard balance widget", () => {
  it("answers 'how much do I owe, and who do I pay?'", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/groups/:groupId/dashboard" element={<DashboardPage />} />
      </Routes>,
      { route: "/groups/1/dashboard" },
    );

    expect(await screen.findByText("You owe")).toBeInTheDocument();
    // The amount is shown as a positive figure under a "You owe" heading.
    await waitFor(() => expect(screen.getAllByText("₹100.00").length).toBeGreaterThan(0));
    expect(screen.getByText(/pay alice to clear it/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settle up/i })).toBeInTheDocument();
  });
});
