/**
 * Mirrors the FastAPI schemas. Every monetary field is typed `string` on purpose --
 * the API sends "33.34", never 33.34, and nothing here should be tempted to do
 * float arithmetic on it. Use the Decimal helpers in lib/money.ts instead.
 */

export interface Envelope<T> {
  success: boolean;
  data: T | null;
  message: string | null;
  error_code?: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export type Role = "admin" | "member" | "viewer";
export type SplitType = "equal" | "exact" | "percentage" | "shares";

export interface User {
  id: number;
  name: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Group {
  id: number;
  name: string;
  currency: string;
  created_by: number;
  is_archived: boolean;
  created_at: string;
  role: Role | null;
  member_count: number | null;
  my_balance: string | null;
}

export interface Member {
  user_id: number;
  name: string;
  email: string;
  role: Role;
  status: "active" | "removed";
  joined_at: string;
}

export interface Invite {
  code: string;
  group_id: number;
  expires_at: string;
  is_revoked: boolean;
}

export interface Split {
  user_id: number;
  amount: string;
  percentage: string | null;
  shares: string | null;
}

export interface Expense {
  id: number;
  group_id: number;
  description: string;
  amount: string;
  currency: string;
  paid_by: number;
  paid_by_name: string | null;
  category_id: number | null;
  category_name: string | null;
  expense_date: string;
  split_type: SplitType;
  notes: string | null;
  created_by: number;
  version: number;
  is_reversed: boolean;
  reversed_by: number | null;
  reversed_at: string | null;
  created_at: string;
  updated_at: string;
  splits: Split[];
  my_share: string | null;
}

export interface ParticipantInput {
  user_id: number;
  amount?: string;
  percentage?: string;
  shares?: string;
}

export interface ExpenseInput {
  description: string;
  amount: string;
  expense_date: string;
  split_type: SplitType;
  category_id: number | null;
  notes: string | null;
  paid_by: number;
  participants: ParticipantInput[];
  version?: number;
}

export interface Balance {
  user_id: number;
  name: string;
  total_paid: string;
  total_share: string;
  settlements_paid: string;
  settlements_received: string;
  balance: string;
}

export interface PairwiseDebt {
  from_user_id: number;
  from_name: string;
  to_user_id: number;
  to_name: string;
  amount: string;
}

export interface GroupBalances {
  group_id: number;
  currency: string;
  balances: Balance[];
  pairwise: PairwiseDebt[];
  my_balance: string;
  total_outstanding: string;
}

export interface Suggestions {
  group_id: number;
  currency: string;
  suggestions: PairwiseDebt[];
  pairwise: PairwiseDebt[];
  you_owe: string;
  you_are_owed: string;
}

export interface Settlement {
  id: number;
  group_id: number;
  from_user_id: number;
  from_name: string | null;
  to_user_id: number;
  to_name: string | null;
  amount: string;
  settlement_date: string;
  notes: string | null;
  created_by: number;
  created_at: string;
  is_reversed: boolean;
  reversed_by: number | null;
  reversed_at: string | null;
}

export interface Category {
  id: number;
  group_id: number | null;
  name: string;
  icon: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Summary {
  group_id: number;
  currency: string;
  total_spend: string;
  expense_count: number;
  member_count: number;
  my_total_paid: string;
  my_total_share: string;
  my_balance: string;
  average_expense: string;
  largest_expense: string;
  first_expense_date: string | null;
  last_expense_date: string | null;
}

export interface CategoryReportRow {
  category_id: number | null;
  category_name: string;
  icon: string | null;
  total: string;
  expense_count: number;
  percentage: string;
}

export interface MemberReportRow {
  user_id: number;
  name: string;
  total_paid: string;
  total_share: string;
  balance: string;
  expense_count: number;
}

export interface MonthlyReportRow {
  month: string;
  total: string;
  expense_count: number;
  my_share: string;
}
