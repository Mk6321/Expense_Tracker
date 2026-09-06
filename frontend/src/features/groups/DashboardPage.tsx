import { motion } from "framer-motion";
import {
  ArrowRight,
  ArrowUpRight,
  Plus,
  Receipt,
  Sparkles,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AnimatedMoney,
  Avatar,
  Card,
  EmptyState,
  Modal,
  PageFade,
  SectionTitle,
  Skeleton,
  Stagger,
  StaggerItem,
  balanceTone,
  cn,
  toast,
} from "../../components/ui";
import { formatMoney, isZero } from "../../lib/money";
import {
  useBalances,
  useExpenses,
  useGroup,
  useReports,
  useSuggestions,
} from "../../lib/queries";
import { useAuth } from "../auth/AuthContext";
import { ExpenseForm } from "../expenses/ExpenseForm";

export default function DashboardPage() {
  const groupId = Number(useParams().groupId);
  const { user } = useAuth();
  const { data: group } = useGroup(groupId);
  const { data: balances, isLoading: balancesLoading } = useBalances(groupId);
  const { data: suggestions } = useSuggestions(groupId);
  const { data: expenses } = useExpenses(groupId, 5);
  const { data: reports } = useReports(groupId);
  const [adding, setAdding] = useState(false);

  const currency = group?.currency ?? "INR";
  const canWrite = group?.role !== "viewer";
  const myBalance = balances?.my_balance ?? "0.00";
  const settled = isZero(myBalance);

  // The one question the app exists to answer, up top.
  const headline = settled
    ? "You're all settled up"
    : myBalance.startsWith("-")
      ? "You owe"
      : "You are owed";

  const myPayments = (suggestions?.suggestions ?? []).filter(
    (item) => item.from_user_id === user?.id,
  );
  const myIncoming = (suggestions?.suggestions ?? []).filter(
    (item) => item.to_user_id === user?.id,
  );

  return (
    <PageFade>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label mb-1">{group?.name}</p>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Dashboard</h1>
        </div>
        {canWrite ? (
          <button onClick={() => setAdding(true)} className="btn-primary">
            <Plus size={16} /> Add expense
          </button>
        ) : null}
      </div>

      {/* ------------------------------------------------------- hero card */}
      {balancesLoading ? (
        <Skeleton className="h-44" />
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        >
          <Card className="relative overflow-hidden p-6 sm:p-8">
            <span
              className={cn(
                "absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent to-transparent",
                settled
                  ? "via-slate-500/40"
                  : myBalance.startsWith("-")
                    ? "via-debit/60"
                    : "via-credit/60",
              )}
            />
            {/* Slow scan line, so the hero never feels completely static. */}
            <span className="animate-scan-line pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-white/[.035] to-transparent" />

            <div className="relative flex flex-wrap items-end justify-between gap-6">
              <div>
                <p className="label mb-2">{headline}</p>
                <AnimatedMoney
                  value={myBalance}
                  currency={currency}
                  absolute
                  className={cn(
                    "text-4xl font-bold sm:text-5xl",
                    settled ? "text-slate-300" : balanceTone(myBalance),
                  )}
                />
                <p className="mt-3 max-w-sm text-xs leading-relaxed text-slate-500">
                  {settled
                    ? "Nothing outstanding in this group."
                    : myPayments.length
                      ? `Pay ${myPayments.map((p) => p.to_name).join(", ")} to clear it.`
                      : myIncoming.length
                        ? `${myIncoming.map((p) => p.from_name).join(", ")} owe you.`
                        : "Across all expenses and settlements in this group."}
                </p>
              </div>

              <Link
                to={`/groups/${groupId}/settle`}
                className="btn-ghost group shrink-0 border-neon-cyan/25 text-neon-cyan hover:border-neon-cyan/50 hover:text-cyan-200"
              >
                Settle up
                <ArrowRight size={15} className="transition-transform group-hover:translate-x-0.5" />
              </Link>
            </div>
          </Card>
        </motion.div>
      )}

      {/* ----------------------------------------------------------- tiles */}
      <Stagger className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StaggerItem>
          <StatTile
            icon={<Wallet size={16} />}
            label="Group total"
            value={formatMoney(reports?.summary.total_spend ?? "0", currency)}
            hint={`${reports?.summary.expense_count ?? 0} expenses`}
          />
        </StaggerItem>
        <StaggerItem>
          <StatTile
            icon={<ArrowUpRight size={16} />}
            label="You paid"
            value={formatMoney(reports?.summary.my_total_paid ?? "0", currency)}
            hint="across this group"
          />
        </StaggerItem>
        <StaggerItem>
          <StatTile
            icon={<Receipt size={16} />}
            label="Your share"
            value={formatMoney(reports?.summary.my_total_share ?? "0", currency)}
            hint="what you consumed"
          />
        </StaggerItem>
        <StaggerItem>
          <StatTile
            icon={<TrendingUp size={16} />}
            label="Outstanding"
            value={formatMoney(balances?.total_outstanding ?? "0", currency)}
            hint="unsettled across the group"
          />
        </StaggerItem>
      </Stagger>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {/* --------------------------------------------------- who owes whom */}
        <div>
          <SectionTitle
            action={
              <Link
                to={`/groups/${groupId}/settle`}
                className="text-[11px] font-semibold text-neon-cyan hover:text-cyan-200"
              >
                See full plan
              </Link>
            }
          >
            Who owes whom
          </SectionTitle>
          <Card className="p-3">
            {!suggestions?.suggestions.length ? (
              <div className="flex items-center gap-3 px-2 py-6 text-sm text-slate-500">
                <Sparkles size={16} className="text-credit" />
                Everyone is square. Nothing to pay.
              </div>
            ) : (
              <ul className="divide-y divide-white/[.05]">
                {suggestions.suggestions.slice(0, 5).map((item, index) => (
                  <motion.li
                    key={`${item.from_user_id}-${item.to_user_id}`}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="flex items-center gap-2.5 px-2 py-2.5"
                  >
                    <Avatar name={item.from_name} id={item.from_user_id} size="sm" />
                    <span className="truncate text-xs text-slate-300">{item.from_name}</span>
                    <ArrowRight size={13} className="shrink-0 text-slate-600" />
                    <Avatar name={item.to_name} id={item.to_user_id} size="sm" />
                    <span className="min-w-0 flex-1 truncate text-xs text-slate-300">
                      {item.to_name}
                    </span>
                    <span className="tabular shrink-0 text-sm font-semibold text-white">
                      {formatMoney(item.amount, currency)}
                    </span>
                  </motion.li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* ------------------------------------------------ recent expenses */}
        <div>
          <SectionTitle
            action={
              <Link
                to={`/groups/${groupId}/expenses`}
                className="text-[11px] font-semibold text-neon-cyan hover:text-cyan-200"
              >
                View all
              </Link>
            }
          >
            Recent activity
          </SectionTitle>
          <Card className="p-3">
            {!expenses?.items.length ? (
              <EmptyState
                title="No expenses yet"
                description="The first one you add shows up here."
              />
            ) : (
              <ul className="divide-y divide-white/[.05]">
                {expenses.items.slice(0, 5).map((expense, index) => (
                  <motion.li
                    key={expense.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className={cn(
                      "flex items-center gap-3 px-2 py-2.5",
                      expense.is_reversed && "opacity-45",
                    )}
                  >
                    <Avatar name={expense.paid_by_name ?? "?"} id={expense.paid_by} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p
                        className={cn(
                          "truncate text-xs font-medium text-slate-200",
                          expense.is_reversed && "line-through",
                        )}
                      >
                        {expense.description}
                      </p>
                      <p className="truncate text-[10px] text-slate-600">
                        {expense.paid_by_name} ·{" "}
                        {new Date(expense.expense_date).toLocaleDateString(undefined, {
                          day: "numeric",
                          month: "short",
                        })}
                      </p>
                    </div>
                    <span className="tabular shrink-0 text-sm font-semibold text-white">
                      {formatMoney(expense.amount, currency)}
                    </span>
                  </motion.li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

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
    </PageFade>
  );
}

function StatTile({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <motion.div whileHover={{ y: -3 }}>
      <Card interactive glow="cyan" className="h-full">
        <div className="mb-3 flex items-center gap-2 text-neon-cyan">
          {icon}
          <span className="label text-slate-500">{label}</span>
        </div>
        <p className="tabular text-xl font-bold text-white">{value}</p>
        <p className="mt-1 text-[11px] text-slate-600">{hint}</p>
      </Card>
    </motion.div>
  );
}
