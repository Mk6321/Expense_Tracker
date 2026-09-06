import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Loader2, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import Decimal from "decimal.js";
import { ErrorNote, Avatar, Segmented, cn } from "../../components/ui";
import { d, formatMoney, previewEqualSplit, sum } from "../../lib/money";
import { toApiError } from "../../lib/api";
import { useCategories, useCreateExpense, useMembers, useUpdateExpense } from "../../lib/queries";
import type { Expense, ExpenseInput, Member, SplitType } from "../../types/api";
import { useAuth } from "../auth/AuthContext";

const SPLIT_OPTIONS: { value: SplitType; label: string }[] = [
  { value: "equal", label: "Equal" },
  { value: "exact", label: "Exact" },
  { value: "percentage", label: "Percent" },
  { value: "shares", label: "Shares" },
];

const today = () => new Date().toISOString().slice(0, 10);

interface Props {
  groupId: number;
  currency: string;
  expense?: Expense;
  onDone: () => void;
}

/**
 * Add/edit expense. The live figures here are display aids computed with decimal.js
 * -- the server recomputes every split and is the only authority on what is saved.
 */
export function ExpenseForm({ groupId, currency, expense, onDone }: Props) {
  const { user } = useAuth();
  const { data: members } = useMembers(groupId);
  const { data: categories } = useCategories(groupId);
  const createExpense = useCreateExpense(groupId);
  const updateExpense = useUpdateExpense(groupId);
  const editing = !!expense;

  const activeMembers = useMemo<Member[]>(
    () =>
      (members ?? []).filter(
        (member) =>
          member.status === "active" ||
          expense?.splits.some((split) => split.user_id === member.user_id),
      ),
    [members, expense],
  );

  const [description, setDescription] = useState(expense?.description ?? "");
  const [amount, setAmount] = useState(expense?.amount ?? "");
  const [expenseDate, setExpenseDate] = useState(expense?.expense_date ?? today());
  const [paidBy, setPaidBy] = useState<number>(expense?.paid_by ?? user?.id ?? 0);
  const [categoryId, setCategoryId] = useState<number | null>(expense?.category_id ?? null);
  const [notes, setNotes] = useState(expense?.notes ?? "");
  const [splitType, setSplitType] = useState<SplitType>(expense?.split_type ?? "equal");
  const [advanced, setAdvanced] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Defaults per Section 11: payer is you, everyone is in, equal, today.
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(expense?.splits.map((split) => split.user_id) ?? []),
  );
  const [values, setValues] = useState<Record<number, string>>(() => {
    const initial: Record<number, string> = {};
    for (const split of expense?.splits ?? []) {
      initial[split.user_id] =
        expense?.split_type === "percentage"
          ? (split.percentage ?? "")
          : expense?.split_type === "shares"
            ? (split.shares ?? "")
            : split.amount;
    }
    return initial;
  });

  // Once the member list arrives on a fresh form, select everyone.
  useEffect(() => {
    if (editing || !activeMembers.length) return;
    setSelected((current) =>
      current.size ? current : new Set(activeMembers.map((member) => member.user_id)),
    );
  }, [activeMembers, editing]);

  useEffect(() => {
    if (!paidBy && user) setPaidBy(user.id);
  }, [paidBy, user]);

  const selectedIds = useMemo(
    () => activeMembers.map((m) => m.user_id).filter((id) => selected.has(id)),
    [activeMembers, selected],
  );

  const total = d(amount || "0");
  const equalPreview = useMemo(
    () => previewEqualSplit(total.toFixed(2), selectedIds),
    [total, selectedIds],
  );

  /** What each person is currently down for, in the unit the split type uses. */
  const allocated = useMemo(() => {
    if (splitType === "equal") return total;
    return sum(selectedIds.map((id) => values[id] ?? "0"));
  }, [splitType, selectedIds, values, total]);

  const target =
    splitType === "percentage"
      ? new Decimal(100)
      : splitType === "shares"
        ? allocated // shares have no fixed target; any positive total works
        : total;

  const remaining = target.minus(allocated);
  const balanced =
    splitType === "equal" ||
    (splitType === "shares" ? allocated.gt(0) : remaining.isZero());

  const canSubmit =
    description.trim().length > 0 &&
    total.gt(0) &&
    selectedIds.length > 0 &&
    paidBy > 0 &&
    balanced &&
    !createExpense.isPending &&
    !updateExpense.isPending;

  const toggle = (userId: number) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  /** Hands the leftover to the last selected person, so a nearly-done split is one click from valid. */
  const fillRemainder = () => {
    const last = selectedIds[selectedIds.length - 1];
    if (last === undefined) return;
    setValues((current) => ({
      ...current,
      [last]: d(current[last] ?? "0").plus(remaining).toFixed(2),
    }));
  };

  const splitEvenly = () => {
    if (splitType === "percentage") {
      const each = new Decimal(100).div(selectedIds.length);
      const next: Record<number, string> = {};
      selectedIds.forEach((id, index) => {
        next[id] =
          index === selectedIds.length - 1
            ? new Decimal(100).minus(each.toDecimalPlaces(2).times(selectedIds.length - 1)).toFixed(2)
            : each.toDecimalPlaces(2).toFixed(2);
      });
      setValues((current) => ({ ...current, ...next }));
    } else if (splitType === "exact") {
      const preview = previewEqualSplit(total.toFixed(2), selectedIds);
      setValues((current) => ({ ...current, ...Object.fromEntries(preview) }));
    } else if (splitType === "shares") {
      setValues((current) => ({
        ...current,
        ...Object.fromEntries(selectedIds.map((id) => [id, "1"])),
      }));
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const input: ExpenseInput = {
      description: description.trim(),
      amount: total.toFixed(2),
      expense_date: expenseDate,
      split_type: splitType,
      category_id: categoryId,
      notes: notes.trim() || null,
      paid_by: paidBy,
      participants: selectedIds.map((id) => ({
        user_id: id,
        ...(splitType === "exact" ? { amount: d(values[id] ?? "0").toFixed(2) } : {}),
        ...(splitType === "percentage" ? { percentage: d(values[id] ?? "0").toFixed(2) } : {}),
        ...(splitType === "shares" ? { shares: d(values[id] ?? "0").toFixed(2) } : {}),
      })),
    };

    try {
      if (editing && expense) {
        await updateExpense.mutateAsync({
          expenseId: expense.id,
          input: { ...input, version: expense.version },
        });
      } else {
        await createExpense.mutateAsync(input);
      }
      onDone();
    } catch (caught) {
      const apiError = toApiError(caught);
      setError(
        apiError.code === "VERSION_CONFLICT"
          ? "Someone else edited this expense while you had it open. Close and reopen it to see their version."
          : apiError.message,
      );
    }
  };

  const unit = splitType === "percentage" ? "%" : splitType === "shares" ? "shares" : currency;

  return (
    <form onSubmit={submit} className="space-y-5">
      {/* ---------------------------------------------------------- basics */}
      <div>
        <label htmlFor="description" className="label mb-1.5 block">
          What was it for?
        </label>
        <input
          id="description"
          className="input"
          placeholder="Dinner at Toit"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          autoFocus
          required
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="amount" className="label mb-1.5 block">
            Amount
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-slate-500">
              {formatMoney("0", currency).replace(/[\d.,]/g, "")}
            </span>
            <input
              id="amount"
              className="input pl-8 text-lg font-semibold tabular"
              inputMode="decimal"
              placeholder="0.00"
              value={amount}
              onChange={(event) =>
                setAmount(event.target.value.replace(/[^\d.]/g, "").slice(0, 12))
              }
              required
            />
          </div>
        </div>
        <div>
          <label htmlFor="date" className="label mb-1.5 block">
            Date
          </label>
          <input
            id="date"
            type="date"
            className="input"
            value={expenseDate}
            onChange={(event) => setExpenseDate(event.target.value)}
            required
          />
        </div>
      </div>

      <div>
        <label htmlFor="paid-by" className="label mb-1.5 block">
          Paid by
        </label>
        <select
          id="paid-by"
          className="input"
          value={paidBy}
          onChange={(event) => setPaidBy(Number(event.target.value))}
        >
          {activeMembers.map((member) => (
            <option key={member.user_id} value={member.user_id} className="bg-void-800">
              {member.name}
              {member.user_id === user?.id ? " (you)" : ""}
            </option>
          ))}
        </select>
      </div>

      {/* ------------------------------------------------------ split setup */}
      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <span className="label">Split</span>
          {splitType !== "equal" ? (
            <button
              type="button"
              onClick={splitEvenly}
              className="text-[11px] font-semibold text-neon-cyan transition hover:text-cyan-200"
            >
              Distribute evenly
            </button>
          ) : null}
        </div>
        <Segmented options={SPLIT_OPTIONS} value={splitType} onChange={setSplitType} />
      </div>

      <div className="space-y-1.5">
        {activeMembers.map((member) => {
          const isSelected = selected.has(member.user_id);
          const preview = equalPreview.get(member.user_id) ?? "0.00";
          return (
            <motion.div
              key={member.user_id}
              layout
              className={cn(
                "flex items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors",
                isSelected
                  ? "border-neon-cyan/25 bg-neon-cyan/[.05]"
                  : "border-white/[.07] bg-white/[.02]",
              )}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => toggle(member.user_id)}
                aria-label={`Include ${member.name}`}
                className="h-4 w-4 shrink-0 accent-cyan-400"
              />
              <Avatar name={member.name} id={member.user_id} size="sm" />
              <span className="min-w-0 flex-1 truncate text-sm text-slate-200">
                {member.name}
                {member.user_id === user?.id ? (
                  <span className="ml-1 text-xs text-slate-500">(you)</span>
                ) : null}
                {member.status === "removed" ? (
                  <span className="ml-1 text-xs text-slate-600">· removed</span>
                ) : null}
              </span>

              {isSelected ? (
                splitType === "equal" ? (
                  <span className="tabular text-sm text-slate-400">
                    {formatMoney(preview, currency)}
                  </span>
                ) : (
                  <input
                    className="input w-24 py-1.5 text-right text-sm tabular"
                    inputMode="decimal"
                    placeholder="0"
                    aria-label={`${member.name} ${unit}`}
                    value={values[member.user_id] ?? ""}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [member.user_id]: event.target.value.replace(/[^\d.]/g, ""),
                      }))
                    }
                  />
                )
              ) : null}
            </motion.div>
          );
        })}
      </div>

      {/* --------------------------------------------------- running total */}
      <AnimatePresence>
        {splitType !== "equal" && selectedIds.length > 0 ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className={cn(
              "flex items-center justify-between overflow-hidden rounded-xl border px-3.5 py-2.5 text-sm",
              balanced
                ? "border-credit/25 bg-credit/[.07] text-credit"
                : "border-neon-amber/25 bg-neon-amber/[.07] text-neon-amber",
            )}
          >
            <span className="text-xs font-medium">
              {splitType === "shares"
                ? `${allocated.toFixed(2)} shares total`
                : balanced
                  ? "Splits add up exactly"
                  : `${remaining.isNegative() ? "Over by" : "Left to allocate"} ${
                      splitType === "percentage"
                        ? `${remaining.abs().toFixed(2)}%`
                        : formatMoney(remaining.abs().toFixed(2), currency)
                    }`}
            </span>
            {!balanced && splitType !== "shares" ? (
              <button
                type="button"
                onClick={fillRemainder}
                className="text-xs font-semibold underline underline-offset-2"
              >
                Give it to the last person
              </button>
            ) : null}
          </motion.div>
        ) : null}
      </AnimatePresence>

      {/* -------------------------------------------------------- advanced */}
      <div>
        <button
          type="button"
          onClick={() => setAdvanced((open) => !open)}
          className="flex w-full items-center justify-between rounded-xl border border-white/[.07] px-3.5 py-2.5 text-xs font-semibold text-slate-400 transition hover:text-white"
        >
          Category and notes
          <ChevronDown
            size={15}
            className={cn("transition-transform", advanced && "rotate-180")}
          />
        </button>
        <AnimatePresence>
          {advanced ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="space-y-4 pt-4">
                <div>
                  <label htmlFor="category" className="label mb-1.5 block">
                    Category
                  </label>
                  <select
                    id="category"
                    className="input"
                    value={categoryId ?? ""}
                    onChange={(event) =>
                      setCategoryId(event.target.value ? Number(event.target.value) : null)
                    }
                  >
                    <option value="" className="bg-void-800">
                      Uncategorised
                    </option>
                    {(categories ?? []).map((category) => (
                      <option key={category.id} value={category.id} className="bg-void-800">
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="notes" className="label mb-1.5 block">
                    Notes
                  </label>
                  <textarea
                    id="notes"
                    className="input min-h-[72px] resize-y"
                    placeholder="Anything worth remembering later"
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                  />
                </div>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      <ErrorNote message={error} />

      <button type="submit" className="btn-primary w-full" disabled={!canSubmit}>
        {createExpense.isPending || updateExpense.isPending ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Save size={16} />
        )}
        {editing ? "Save changes" : "Add expense"}
      </button>
      {!balanced ? (
        <p className="text-center text-[11px] text-slate-500">
          Splits must add up before this can be saved.
        </p>
      ) : null}
    </form>
  );
}
