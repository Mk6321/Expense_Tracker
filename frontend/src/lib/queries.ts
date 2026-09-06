import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { api, unwrap } from "./api";
import type {
  Category,
  CategoryReportRow,
  Envelope,
  Expense,
  ExpenseInput,
  Group,
  GroupBalances,
  Invite,
  Member,
  MemberReportRow,
  MonthlyReportRow,
  Page,
  Role,
  Settlement,
  Suggestions,
  Summary,
} from "../types/api";

/** One place for every key, so invalidation cannot drift out of sync. */
export const keys = {
  groups: ["groups"] as const,
  group: (id: number) => ["group", id] as const,
  members: (id: number) => ["members", id] as const,
  categories: (id: number) => ["categories", id] as const,
  expenses: (id: number) => ["expenses", id] as const,
  expense: (id: number) => ["expense", id] as const,
  balances: (id: number) => ["balances", id] as const,
  suggestions: (id: number) => ["settlement-suggestions", id] as const,
  settlements: (id: number) => ["settlements", id] as const,
  reports: (id: number) => ["reports", id] as const,
};

/**
 * Anything that moves money invalidates the whole derived set. Balances, reports
 * and suggestions are all computed from the same rows, so refreshing one without
 * the others would show a self-contradictory screen.
 */
function useLedgerInvalidation(groupId: number) {
  const queryClient = useQueryClient();
  return () => {
    for (const key of [
      keys.expenses(groupId),
      keys.balances(groupId),
      keys.suggestions(groupId),
      keys.settlements(groupId),
      keys.reports(groupId),
      keys.group(groupId),
      keys.groups,
    ]) {
      queryClient.invalidateQueries({ queryKey: key });
    }
  };
}

export function useGroups() {
  return useQuery({
    queryKey: keys.groups,
    queryFn: () => unwrap<Group[]>(api.get<Envelope<Group[]>>("/groups")),
  });
}

export function useGroup(groupId: number) {
  return useQuery({
    queryKey: keys.group(groupId),
    queryFn: () => unwrap<Group>(api.get<Envelope<Group>>(`/groups/${groupId}`)),
    enabled: Number.isFinite(groupId) && groupId > 0,
  });
}

export function useMembers(groupId: number) {
  return useQuery({
    queryKey: keys.members(groupId),
    queryFn: () => unwrap<Member[]>(api.get<Envelope<Member[]>>(`/groups/${groupId}/members`)),
    enabled: groupId > 0,
  });
}

export function useCategories(groupId: number) {
  return useQuery({
    queryKey: keys.categories(groupId),
    queryFn: () =>
      unwrap<Category[]>(api.get<Envelope<Category[]>>(`/groups/${groupId}/categories`)),
    enabled: groupId > 0,
    staleTime: 5 * 60 * 1000,
  });
}

export function useExpenses(groupId: number, limit = 50) {
  return useQuery({
    queryKey: keys.expenses(groupId),
    queryFn: () =>
      unwrap<Page<Expense>>(
        api.get<Envelope<Page<Expense>>>(`/groups/${groupId}/expenses`, {
          params: { limit },
        }),
      ),
    enabled: groupId > 0,
  });
}

export function useExpense(expenseId: number) {
  return useQuery({
    queryKey: keys.expense(expenseId),
    queryFn: () => unwrap<Expense>(api.get<Envelope<Expense>>(`/expenses/${expenseId}`)),
    enabled: expenseId > 0,
  });
}

export function useBalances(groupId: number) {
  return useQuery({
    queryKey: keys.balances(groupId),
    queryFn: () =>
      unwrap<GroupBalances>(api.get<Envelope<GroupBalances>>(`/groups/${groupId}/balances`)),
    enabled: groupId > 0,
  });
}

export function useSuggestions(groupId: number) {
  return useQuery({
    queryKey: keys.suggestions(groupId),
    queryFn: () =>
      unwrap<Suggestions>(
        api.get<Envelope<Suggestions>>(`/groups/${groupId}/settlement-suggestions`),
      ),
    enabled: groupId > 0,
  });
}

export function useSettlements(groupId: number) {
  return useQuery({
    queryKey: keys.settlements(groupId),
    queryFn: () =>
      unwrap<Page<Settlement>>(
        api.get<Envelope<Page<Settlement>>>(`/groups/${groupId}/settlements`),
      ),
    enabled: groupId > 0,
  });
}

export function useReports(groupId: number) {
  return useQuery({
    queryKey: keys.reports(groupId),
    queryFn: async () => {
      const [summary, categories, members, monthly] = await Promise.all([
        unwrap<Summary>(api.get<Envelope<Summary>>(`/groups/${groupId}/reports/summary`)),
        unwrap<CategoryReportRow[]>(
          api.get<Envelope<CategoryReportRow[]>>(`/groups/${groupId}/reports/categories`),
        ),
        unwrap<MemberReportRow[]>(
          api.get<Envelope<MemberReportRow[]>>(`/groups/${groupId}/reports/members`),
        ),
        unwrap<MonthlyReportRow[]>(
          api.get<Envelope<MonthlyReportRow[]>>(`/groups/${groupId}/reports/monthly`),
        ),
      ]);
      return { summary, categories, members, monthly };
    },
    enabled: groupId > 0,
  });
}

/** A fresh key per submission attempt, so a retry after a timeout cannot double-post. */
function idempotencyKey(): string {
  return crypto.randomUUID();
}

export function useCreateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; currency: string }) =>
      unwrap<Group>(api.post<Envelope<Group>>("/groups", input)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.groups }),
  });
}

export function useJoinGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invite_code: string) =>
      unwrap<Group>(api.post<Envelope<Group>>("/groups/join", { invite_code })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.groups }),
  });
}

export function useCreateInvite(groupId: number) {
  return useMutation({
    mutationFn: () => unwrap<Invite>(api.post<Envelope<Invite>>(`/groups/${groupId}/invites`)),
  });
}

export function useChangeRole(groupId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: Role }) =>
      unwrap<Member>(
        api.put<Envelope<Member>>(`/groups/${groupId}/members/${userId}/role`, { role }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.members(groupId) }),
  });
}

export function useRemoveMember(groupId: number) {
  const invalidate = useLedgerInvalidation(groupId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, force }: { userId: number; force?: boolean }) =>
      unwrap(
        api.delete(`/groups/${groupId}/members/${userId}`, { params: { force: !!force } }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.members(groupId) });
      invalidate();
    },
  });
}

export function useCreateExpense(groupId: number) {
  const invalidate = useLedgerInvalidation(groupId);
  return useMutation({
    mutationFn: (input: ExpenseInput) =>
      unwrap<Expense>(
        api.post<Envelope<Expense>>(`/groups/${groupId}/expenses`, input, {
          headers: { "Idempotency-Key": idempotencyKey() },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useUpdateExpense(groupId: number) {
  const invalidate = useLedgerInvalidation(groupId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ expenseId, input }: { expenseId: number; input: ExpenseInput }) =>
      unwrap<Expense>(api.put<Envelope<Expense>>(`/expenses/${expenseId}`, input)),
    onSuccess: (expense) => {
      queryClient.invalidateQueries({ queryKey: keys.expense(expense.id) });
      invalidate();
    },
  });
}

export function useReverseExpense(groupId: number) {
  const invalidate = useLedgerInvalidation(groupId);
  return useMutation({
    mutationFn: (expenseId: number) =>
      unwrap<Expense>(api.delete<Envelope<Expense>>(`/expenses/${expenseId}`)),
    onSuccess: invalidate,
  });
}

export function useCreateSettlement(groupId: number) {
  const invalidate = useLedgerInvalidation(groupId);
  return useMutation({
    mutationFn: (input: {
      from_user_id: number;
      to_user_id: number;
      amount: string;
      settlement_date: string;
      notes?: string | null;
    }) =>
      unwrap<Settlement>(
        api.post<Envelope<Settlement>>(`/groups/${groupId}/settlements`, input, {
          headers: { "Idempotency-Key": idempotencyKey() },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useReverseSettlement(groupId: number) {
  const invalidate = useLedgerInvalidation(groupId);
  return useMutation({
    mutationFn: (settlementId: number) =>
      unwrap<Settlement>(api.delete<Envelope<Settlement>>(`/settlements/${settlementId}`)),
    onSuccess: invalidate,
  });
}

export function useCreateCategory(groupId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; icon?: string | null }) =>
      unwrap<Category>(api.post<Envelope<Category>>(`/groups/${groupId}/categories`, input)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.categories(groupId) }),
  });
}

export type MutationOpts<TData, TVars> = UseMutationOptions<TData, unknown, TVars>;
