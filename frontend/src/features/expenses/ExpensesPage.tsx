import { AnimatePresence, motion } from "framer-motion";
import {
  Pencil,
  Plus,
  Receipt,
  RotateCcw,
  Search,
  Undo2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Avatar,
  Card,
  EmptyState,
  Modal,
  PageFade,
  SectionTitle,
  Skeleton,
  Stagger,
  StaggerItem,
  cn,
  toast,
} from "../../components/ui";
import { toApiError } from "../../lib/api";
import { formatMoney } from "../../lib/money";
import { useExpenses, useGroup, useReverseExpense } from "../../lib/queries";
import type { Expense } from "../../types/api";
import { useAuth } from "../auth/AuthContext";
import { ExpenseForm } from "./ExpenseForm";

export default function ExpensesPage() {
  const groupId = Number(useParams().groupId);
  const { data: group } = useGroup(groupId);
  const { data: page, isLoading } = useExpenses(groupId);
  const { user } = useAuth();
  const reverseExpense = useReverseExpense(groupId);

  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [confirming, setConfirming] = useState<Expense | null>(null);
  const [query, setQuery] = useState("");
  const [showReversed, setShowReversed] = useState(false);

  const currency = group?.currency ?? "INR";
  const canWrite = group?.role !== "viewer";

  const visible = useMemo(() => {
    const items = page?.items ?? [];
    const needle = query.trim().toLowerCase();
    return items.filter((expense) => {
      if (!showReversed && expense.is_reversed) return false;
      if (!needle) return true;
      return (
        expense.description.toLowerCase().includes(needle) ||
        (expense.paid_by_name ?? "").toLowerCase().includes(needle) ||
        (expense.category_name ?? "").toLowerCase().includes(needle)
      );
    });
  }, [page, query, showReversed]);

  const reversedCount = (page?.items ?? []).filter((e) => e.is_reversed).length;

  const canEdit = (expense: Expense) =>
    canWrite && !expense.is_reversed && (expense.created_by === user?.id || group?.role === "admin");

  const doReverse = async () => {
    if (!confirming) return;
    try {
      await reverseExpense.mutateAsync(confirming.id);
      toast("Expense reversed. It stays in the history.");
      setConfirming(null);
    } catch (caught) {
      toast(toApiError(caught).message, "bad");
    }
  };

  return (
    <PageFade>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label mb-1">{group?.name}</p>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Expenses</h1>
        </div>
        {canWrite ? (
          <button onClick={() => setAdding(true)} className="btn-primary">
            <Plus size={16} /> Add expense
          </button>
        ) : null}
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1">
          <Search
            size={15}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-600"
          />
          <input
            className="input pl-9"
            placeholder="Search description, payer or category"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search expenses"
          />
        </div>
        {reversedCount > 0 ? (
          <button
            onClick={() => setShowReversed((current) => !current)}
            className={cn("btn-ghost shrink-0", showReversed && "border-neon-cyan/30 text-white")}
          >
            <RotateCcw size={14} />
            {showReversed ? "Hide" : "Show"} reversed ({reversedCount})
          </button>
        ) : null}
      </div>

      {isLoading ? (
        <div className="space-y-2.5">
          {[0, 1, 2, 3].map((n) => (
            <Skeleton key={n} className="h-[74px]" />
          ))}
        </div>
      ) : !visible.length ? (
        <EmptyState
          icon={<Receipt size={22} />}
          title={query ? "Nothing matches that search" : "No expenses yet"}
          description={
            query
              ? "Try a different word, or clear the search."
              : "Add the first one and everyone's balance updates instantly."
          }
          action={
            canWrite && !query ? (
              <button onClick={() => setAdding(true)} className="btn-primary">
                <Plus size={16} /> Add expense
              </button>
            ) : null
          }
        />
      ) : (
        <Stagger className="space-y-2.5">
          <AnimatePresence mode="popLayout">
            {visible.map((expense) => (
              <StaggerItem key={expense.id}>
                <motion.div layout exit={{ opacity: 0, x: -12 }}>
                  <Card
                    className={cn(
                      "group flex items-center gap-3.5 p-3.5 sm:gap-4 sm:p-4",
                      expense.is_reversed && "opacity-50",
                    )}
                  >
                    <Avatar
                      name={expense.paid_by_name ?? "?"}
                      id={expense.paid_by}
                      size="md"
                    />

                    <div className="min-w-0 flex-1">
                      <p
                        className={cn(
                          "truncate text-sm font-semibold text-white",
                          expense.is_reversed && "line-through",
                        )}
                      >
                        {expense.description}
                      </p>
                      <p className="mt-0.5 truncate text-[11px] text-slate-500">
                        {expense.paid_by_name} paid ·{" "}
                        {new Date(expense.expense_date).toLocaleDateString(undefined, {
                          day: "numeric",
                          month: "short",
                        })}
                        {expense.category_name ? ` · ${expense.category_name}` : ""}
                        {expense.split_type !== "equal" ? ` · ${expense.split_type}` : ""}
                      </p>
                    </div>

                    <div className="shrink-0 text-right">
                      <p className="tabular text-sm font-semibold text-white">
                        {formatMoney(expense.amount, currency)}
                      </p>
                      {expense.my_share && expense.my_share !== "0.00" ? (
                        <p className="tabular mt-0.5 text-[11px] text-slate-500">
                          your share {formatMoney(expense.my_share, currency)}
                        </p>
                      ) : null}
                    </div>

                    {canEdit(expense) ? (
                      <div className="flex shrink-0 gap-1 opacity-100 transition-opacity lg:opacity-0 lg:group-hover:opacity-100">
                        <button
                          onClick={() => setEditing(expense)}
                          aria-label={`Edit ${expense.description}`}
                          className="rounded-lg p-2 text-slate-500 transition hover:bg-white/10 hover:text-neon-cyan"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => setConfirming(expense)}
                          aria-label={`Reverse ${expense.description}`}
                          className="rounded-lg p-2 text-slate-500 transition hover:bg-white/10 hover:text-debit"
                        >
                          <Undo2 size={14} />
                        </button>
                      </div>
                    ) : null}
                  </Card>
                </motion.div>
              </StaggerItem>
            ))}
          </AnimatePresence>
        </Stagger>
      )}

      {page?.next_cursor ? (
        <p className="mt-5 text-center text-xs text-slate-600">
          Showing the {visible.length} most recent. Older ones load as the group grows.
        </p>
      ) : null}

      <Modal open={adding} onClose={() => setAdding(false)} title="Add an expense" wide>
        <ExpenseForm
          groupId={groupId}
          currency={currency}
          onDone={() => {
            setAdding(false);
            toast("Expense added.");
          }}
        />
      </Modal>

      <Modal open={!!editing} onClose={() => setEditing(null)} title="Edit expense" wide>
        {editing ? (
          <ExpenseForm
            groupId={groupId}
            currency={currency}
            expense={editing}
            onDone={() => {
              setEditing(null);
              toast("Expense updated.");
            }}
          />
        ) : null}
      </Modal>

      <Modal open={!!confirming} onClose={() => setConfirming(null)} title="Reverse this expense?">
        <div className="space-y-4">
          <p className="text-sm leading-relaxed text-slate-400">
            <span className="font-semibold text-white">{confirming?.description}</span> will stop
            counting towards anyone's balance. Nothing is deleted — the record stays in the
            history and can still be seen.
          </p>
          <SectionTitle>Effect</SectionTitle>
          <p className="tabular text-sm text-slate-400">
            {formatMoney(confirming?.amount ?? "0", currency)} comes back out of the ledger.
          </p>
          <div className="flex gap-2 pt-1">
            <button onClick={() => setConfirming(null)} className="btn-ghost flex-1">
              Keep it
            </button>
            <button
              onClick={doReverse}
              disabled={reverseExpense.isPending}
              className="btn-danger flex-1"
            >
              <Undo2 size={15} /> Reverse
            </button>
          </div>
        </div>
      </Modal>
    </PageFade>
  );
}
