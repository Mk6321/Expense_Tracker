import { motion } from "framer-motion";
import { BarChart3, CalendarDays, PieChart, Users } from "lucide-react";
import { useParams } from "react-router-dom";
import {
  Avatar,
  Card,
  EmptyState,
  Meter,
  PageFade,
  SectionTitle,
  Skeleton,
  Stagger,
  StaggerItem,
  balanceTone,
  cn,
} from "../../components/ui";
import { d, formatMoney } from "../../lib/money";
import { useGroup, useReports } from "../../lib/queries";

export default function ReportsPage() {
  const groupId = Number(useParams().groupId);
  const { data: group } = useGroup(groupId);
  const { data: reports, isLoading } = useReports(groupId);
  const currency = group?.currency ?? "INR";

  if (isLoading) {
    return (
      <PageFade>
        <div className="space-y-4">
          <Skeleton className="h-28" />
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </PageFade>
    );
  }

  if (!reports || reports.summary.expense_count === 0) {
    return (
      <PageFade>
        <h1 className="mb-6 text-2xl font-bold tracking-tight text-white sm:text-3xl">Reports</h1>
        <EmptyState
          icon={<BarChart3 size={22} />}
          title="Nothing to report yet"
          description="Add a few expenses and the breakdowns by category, member and month appear here."
        />
      </PageFade>
    );
  }

  const { summary, categories, members, monthly } = reports;
  const peakMonth = monthly.reduce(
    (max, row) => (d(row.total).gt(d(max.total)) ? row : max),
    monthly[0],
  );

  return (
    <PageFade>
      <div className="mb-6">
        <p className="label mb-1">{group?.name}</p>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Reports</h1>
      </div>

      <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Total spend", value: formatMoney(summary.total_spend, currency) },
          { label: "Expenses", value: String(summary.expense_count) },
          { label: "Average", value: formatMoney(summary.average_expense, currency) },
          { label: "Largest", value: formatMoney(summary.largest_expense, currency) },
        ].map((tile) => (
          <StaggerItem key={tile.label}>
            <Card className="h-full">
              <p className="label mb-2">{tile.label}</p>
              <p className="tabular text-xl font-bold text-white">{tile.value}</p>
            </Card>
          </StaggerItem>
        ))}
      </Stagger>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {/* ------------------------------------------------------ categories */}
        <div>
          <SectionTitle>
            <span className="flex items-center gap-2">
              <PieChart size={14} /> By category
            </span>
          </SectionTitle>
          <Card className="space-y-4">
            {categories.map((row, index) => (
              <motion.div
                key={row.category_id ?? "none"}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <div className="mb-1.5 flex items-baseline justify-between gap-3">
                  <span className="truncate text-xs font-medium text-slate-200">
                    {row.category_name}
                    <span className="ml-1.5 text-[10px] text-slate-600">
                      {row.expense_count}×
                    </span>
                  </span>
                  <span className="tabular shrink-0 text-xs font-semibold text-white">
                    {formatMoney(row.total, currency)}
                    <span className="ml-1.5 text-[10px] font-normal text-slate-500">
                      {row.percentage}%
                    </span>
                  </span>
                </div>
                <Meter percent={Number(row.percentage)} tone={index % 2 ? "violet" : "cyan"} />
              </motion.div>
            ))}
          </Card>
        </div>

        {/* --------------------------------------------------------- members */}
        <div>
          <SectionTitle>
            <span className="flex items-center gap-2">
              <Users size={14} /> By member
            </span>
          </SectionTitle>
          <Card className="p-3">
            <ul className="divide-y divide-white/[.05]">
              {members.map((row, index) => (
                <motion.li
                  key={row.user_id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="flex items-center gap-3 px-2 py-3"
                >
                  <Avatar name={row.name} id={row.user_id} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-slate-200">{row.name}</p>
                    <p className="tabular truncate text-[10px] text-slate-600">
                      paid {formatMoney(row.total_paid, currency)} · share{" "}
                      {formatMoney(row.total_share, currency)}
                    </p>
                  </div>
                  <span
                    className={cn("tabular shrink-0 text-sm font-semibold", balanceTone(row.balance))}
                  >
                    {formatMoney(row.balance, currency, { signed: true })}
                  </span>
                </motion.li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      {/* ----------------------------------------------------------- monthly */}
      <div className="mt-6">
        <SectionTitle>
          <span className="flex items-center gap-2">
            <CalendarDays size={14} /> Month by month
          </span>
        </SectionTitle>
        <Card>
          {/* Simple bar chart -- heights are relative to the busiest month. */}
          <div className="flex items-end gap-2 overflow-x-auto pb-2" style={{ minHeight: 160 }}>
            {monthly.map((row, index) => {
              const height = peakMonth
                ? d(row.total).div(d(peakMonth.total)).times(120).toNumber()
                : 0;
              return (
                <div key={row.month} className="flex min-w-[52px] flex-1 flex-col items-center gap-2">
                  <span className="tabular text-[10px] text-slate-500">
                    {formatMoney(row.total, currency)}
                  </span>
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: Math.max(height, 4) }}
                    transition={{ delay: index * 0.06, type: "spring", stiffness: 70, damping: 16 }}
                    className="w-full rounded-t-lg bg-gradient-to-t from-violet-500/70 to-cyan-300/90 shadow-glow-cyan"
                    title={`${row.expense_count} expenses`}
                  />
                  <span className="text-[10px] font-medium text-slate-500">
                    {new Date(`${row.month}-01`).toLocaleDateString(undefined, {
                      month: "short",
                      year: "2-digit",
                    })}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-3 border-t border-white/[.06] pt-3 text-[11px] text-slate-600">
            Your share across all months:{" "}
            <span className="tabular text-slate-400">
              {formatMoney(summary.my_total_share, currency)}
            </span>
          </p>
        </Card>
      </div>
    </PageFade>
  );
}
