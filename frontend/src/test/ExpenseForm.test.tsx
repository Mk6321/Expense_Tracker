import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ExpenseForm } from "../features/expenses/ExpenseForm";
import { renderWithProviders } from "./utils";
import type { Member } from "../types/api";

const MEMBERS: Member[] = [
  {
    user_id: 1,
    name: "Alice",
    email: "alice@example.com",
    role: "admin",
    status: "active",
    joined_at: "2026-01-01T00:00:00Z",
  },
  {
    user_id: 2,
    name: "Bob",
    email: "bob@example.com",
    role: "member",
    status: "active",
    joined_at: "2026-01-01T00:00:00Z",
  },
  {
    user_id: 3,
    name: "Cara",
    email: "cara@example.com",
    role: "member",
    status: "active",
    joined_at: "2026-01-01T00:00:00Z",
  },
];

const createExpense = vi.fn();

vi.mock("../features/auth/AuthContext", async () => {
  const actual = await vi.importActual<object>("../features/auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { id: 1, name: "Alice", email: "alice@example.com", is_active: true, created_at: "" },
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
    useMembers: () => ({ data: MEMBERS, isLoading: false }),
    useCategories: () => ({ data: [], isLoading: false }),
    useCreateExpense: () => ({ mutateAsync: createExpense, isPending: false }),
    useUpdateExpense: () => ({ mutateAsync: vi.fn(), isPending: false }),
  };
});

function setup() {
  const onDone = vi.fn();
  renderWithProviders(<ExpenseForm groupId={1} currency="INR" onDone={onDone} />);
  return { onDone, submit: () => screen.getByRole("button", { name: /add expense/i }) };
}

describe("ExpenseForm", () => {
  beforeEach(() => {
    createExpense.mockReset();
    createExpense.mockResolvedValue({ id: 1 });
  });

  it("defaults to everyone, split equally, paid by the current user", async () => {
    setup();
    await waitFor(() => {
      for (const name of ["Alice", "Bob", "Cara"]) {
        expect(screen.getByLabelText(`Include ${name}`)).toBeChecked();
      }
    });
    expect(screen.getByLabelText(/paid by/i)).toHaveValue("1");
  });

  it("previews the equal split as you type an amount", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByLabelText(/^amount$/i), "100");

    // Largest-remainder: the extra cent lands on the lowest user_id.
    await waitFor(() => {
      expect(screen.getByText("₹33.34")).toBeInTheDocument();
      expect(screen.getAllByText("₹33.33")).toHaveLength(2);
    });
  });

  it("submits an equal split with every participant", async () => {
    const user = userEvent.setup();
    const { submit } = setup();

    await user.type(screen.getByLabelText(/what was it for/i), "Dinner");
    await user.type(screen.getByLabelText(/^amount$/i), "90");
    await waitFor(() => expect(submit()).toBeEnabled());
    await user.click(submit());

    await waitFor(() => expect(createExpense).toHaveBeenCalledTimes(1));
    const payload = createExpense.mock.calls[0][0];
    expect(payload).toMatchObject({
      description: "Dinner",
      amount: "90.00",
      split_type: "equal",
      paid_by: 1,
    });
    expect(payload.participants.map((p: { user_id: number }) => p.user_id)).toEqual([1, 2, 3]);
  });

  it("excludes anyone unchecked", async () => {
    const user = userEvent.setup();
    const { submit } = setup();

    await user.type(screen.getByLabelText(/what was it for/i), "Cab");
    await user.type(screen.getByLabelText(/^amount$/i), "50");
    await user.click(screen.getByLabelText("Include Cara"));
    await user.click(submit());

    await waitFor(() => expect(createExpense).toHaveBeenCalled());
    expect(
      createExpense.mock.calls[0][0].participants.map((p: { user_id: number }) => p.user_id),
    ).toEqual([1, 2]);
  });

  describe("split-total validation", () => {
    it("blocks submit while an exact split does not add up", async () => {
      const user = userEvent.setup();
      const { submit } = setup();

      await user.type(screen.getByLabelText(/what was it for/i), "Groceries");
      await user.type(screen.getByLabelText(/^amount$/i), "100");
      await user.click(screen.getByRole("button", { name: "Exact" }));

      await user.type(screen.getByLabelText("Alice INR"), "40");
      await user.type(screen.getByLabelText("Bob INR"), "30");
      // Cara is left at 0 -- 30 short.

      expect(await screen.findByText(/left to allocate/i)).toBeInTheDocument();
      expect(submit()).toBeDisabled();
      expect(screen.getByText(/splits must add up/i)).toBeInTheDocument();

      await user.click(submit());
      expect(createExpense).not.toHaveBeenCalled();
    });

    it("enables submit once the exact split balances", async () => {
      const user = userEvent.setup();
      const { submit } = setup();

      await user.type(screen.getByLabelText(/what was it for/i), "Groceries");
      await user.type(screen.getByLabelText(/^amount$/i), "100");
      await user.click(screen.getByRole("button", { name: "Exact" }));

      await user.type(screen.getByLabelText("Alice INR"), "40");
      await user.type(screen.getByLabelText("Bob INR"), "30");
      await user.type(screen.getByLabelText("Cara INR"), "30");

      expect(await screen.findByText(/splits add up exactly/i)).toBeInTheDocument();
      await waitFor(() => expect(submit()).toBeEnabled());

      await user.click(submit());
      await waitFor(() => expect(createExpense).toHaveBeenCalled());
      expect(createExpense.mock.calls[0][0].participants).toEqual([
        { user_id: 1, amount: "40.00" },
        { user_id: 2, amount: "30.00" },
        { user_id: 3, amount: "30.00" },
      ]);
    });

    it("blocks a percentage split that does not reach 100", async () => {
      const user = userEvent.setup();
      const { submit } = setup();

      await user.type(screen.getByLabelText(/what was it for/i), "Rent");
      await user.type(screen.getByLabelText(/^amount$/i), "3000");
      await user.click(screen.getByRole("button", { name: "Percent" }));

      await user.type(screen.getByLabelText("Alice %"), "50");
      await user.type(screen.getByLabelText("Bob %"), "30");

      expect(await screen.findByText(/left to allocate 20/i)).toBeInTheDocument();
      expect(submit()).toBeDisabled();
    });

    it("flags an over-allocated split too", async () => {
      const user = userEvent.setup();
      const { submit } = setup();

      await user.type(screen.getByLabelText(/what was it for/i), "Rent");
      await user.type(screen.getByLabelText(/^amount$/i), "100");
      await user.click(screen.getByRole("button", { name: "Exact" }));
      await user.type(screen.getByLabelText("Alice INR"), "200");

      expect(await screen.findByText(/over by/i)).toBeInTheDocument();
      expect(submit()).toBeDisabled();
    });

    it("distributes evenly on demand", async () => {
      const user = userEvent.setup();
      const { submit } = setup();

      await user.type(screen.getByLabelText(/what was it for/i), "Dinner");
      await user.type(screen.getByLabelText(/^amount$/i), "100");
      await user.click(screen.getByRole("button", { name: "Exact" }));
      await user.click(screen.getByRole("button", { name: /distribute evenly/i }));

      expect(await screen.findByText(/splits add up exactly/i)).toBeInTheDocument();
      await waitFor(() => expect(submit()).toBeEnabled());
    });
  });

  it("will not submit without a description or a positive amount", async () => {
    const user = userEvent.setup();
    const { submit } = setup();
    expect(submit()).toBeDisabled();

    await user.type(screen.getByLabelText(/what was it for/i), "Something");
    expect(submit()).toBeDisabled();

    await user.type(screen.getByLabelText(/^amount$/i), "0");
    expect(submit()).toBeDisabled();
  });

  it("blocks submit when nobody is selected", async () => {
    const user = userEvent.setup();
    const { submit } = setup();

    await user.type(screen.getByLabelText(/what was it for/i), "Solo");
    await user.type(screen.getByLabelText(/^amount$/i), "10");
    for (const name of ["Alice", "Bob", "Cara"]) {
      await user.click(screen.getByLabelText(`Include ${name}`));
    }
    expect(submit()).toBeDisabled();
  });

  it("explains a version conflict in plain language", async () => {
    const user = userEvent.setup();
    createExpense.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 409,
        data: { message: "Conflict", error_code: "VERSION_CONFLICT" },
      },
    });
    const { submit } = setup();

    await user.type(screen.getByLabelText(/what was it for/i), "Dinner");
    await user.type(screen.getByLabelText(/^amount$/i), "30");
    await user.click(submit());

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/someone else edited this expense/i)).toBeInTheDocument();
  });
});
