import { motion } from "framer-motion";
import { ArrowRight, Handshake, Loader2, Sparkles, Undo2 } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  Avatar,
  Card,
  EmptyState,
  ErrorNote,
  Modal,
  PageFade,
  SectionTitle,
  Segmented,
  Skeleton,
  Stagger,
  StaggerItem,
  balanceTone,
  cn,
  toast,
} from "../../components/ui";
import { toApiError } from "../../lib/api";
import { formatMoney } from "../../lib/money";
import {
  useCreateSettlement,
  useGroup,
  useMembers,
  useReverseSettlement,
  useSettlements,
  useSuggestions,
} from "../../lib/queries";
import type { PairwiseDebt } from "../../types/api";
import { useAuth } from "../auth/AuthContext";

type View = "simplified" | "detailed";

export default function SettleUpPage() {
  const groupId = Number(useParams().groupId);
  const { user } = useAuth();
  const { data: group } = useGroup(groupId);
  const { data: suggestions, isLoading } = useSuggestions(groupId);
  const { data: settlements } = useSettlements(groupId);
  const reverseSettlement = useReverseSettlement(groupId);

  const [view, setView] = useState<View>("simplified");
  const [recording, setRecording] = useState<PairwiseDebt | null>(null);
  const [freeform, setFreeform] = useState(false);

  const currency = group?.currency ?? "INR";
  const canWrite = group?.role !== "viewer";
  const rows = view === "simplified" ? suggestions?.suggestions : suggestions?.pairwise;

  const undo = async (settlementId: number) => {
    try {
      await reverseSettlement.mutateAsync(settlementId);
      toast("Settlement reversed.");
    } catch (caught) {
      toast(toApiError(caught).message, "bad");
    }
  };

  return (
    <PageFade>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label mb-1">{group?.name}</p>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Settle up</h1>
        </div>
        {canWrite ? (
          <button onClick={() => setFreeform(true)} className="btn-ghost">
            <Handshake size={15} /> Record a payment
          </button>
        ) : null}
      </div>

      <div className="mb-5 grid gap-4 sm:grid-cols-2">
        <Card>
          <p className="label mb-2">You owe</p>
          <p className={cn("tabular text-2xl font-bold", balanceTone(`-${suggestions?.you_owe ?? "0"}`))}>
            {formatMoney(suggestions?.you_owe ?? "0", currency)}
          </p>
        </Card>
        <Card>
          <p className="label mb-2">You are owed</p>
          <p className="tabular text-2xl font-bold text-credit">
            {formatMoney(suggestions?.you_are_owed ?? "0", currency)}
          </p>
        </Card>
      </div>

      <SectionTitle>Payment plan</SectionTitle>
      <div className="mb-3 max-w-xs">
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { value: "simplified", label: "Simplified" },
            { value: "detailed", label: "Who paid what" },
          ]}
        />
      </div>
      <p className="mb-4 text-xs leading-relaxed text-slate-500">
        {view === "simplified"
          ? "The fewest transfers that clear everyone. Some pairings may not match a specific shared expense — switch to the detailed view to see the real debts."
          : "Actual debts from shared expenses, unsimplified. More transfers, but every line traces back to something you both paid for."}
      </p>

      {isLoading ? (
        <div className="space-y-2.5">
          {[0, 1, 2].map((n) => (
            <Skeleton key={n} className="h-16" />
          ))}
        </div>
      ) : !rows?.length ? (
        <EmptyState
          icon={<Sparkles size={22} />}
          title="Everyone is settled up"
          description="No outstanding balances in this group. Add an expense and this fills in again."
        />
      ) : (
        <Stagger className="space-y-2.5">
          {rows.map((row) => {
            const mine = row.from_user_id === user?.id;
            const incoming = row.to_user_id === user?.id;
            return (
              <StaggerItem key={`${row.from_user_id}-${row.to_user_id}`}>
                <motion.div whileHover={{ x: 3 }}>
                  <Card
                    className={cn(
                      "flex flex-wrap items-center gap-3 p-4",
                      mine && "border-debit/25 bg-debit/[.04]",
                      incoming && "border-credit/25 bg-credit/[.04]",
                    )}
                  >
                    <Avatar name={row.from_name} id={row.from_user_id} />
                    <span className="text-sm font-medium text-slate-200">
                      {mine ? "You" : row.from_name}
                    </span>
                    <ArrowRight size={16} className="text-slate-600" />
                    <Avatar name={row.to_name} id={row.to_user_id} />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-200">
                      {incoming ? "You" : row.to_name}
                    </span>
                    <span className="tabular text-base font-bold text-white">
                      {formatMoney(row.amount, currency)}
                    </span>
                    {canWrite && (mine || incoming || group?.role === "admin") ? (
                      <button onClick={() => setRecording(row)} className="btn-ghost py-1.5 text-xs">
                        Mark paid
                      </button>
                    ) : null}
                  </Card>
                </motion.div>
              </StaggerItem>
            );
          })}
        </Stagger>
      )}

      {/* ------------------------------------------------------------ history */}
      {settlements?.items.length ? (
        <div className="mt-8">
          <SectionTitle>Settlement history</SectionTitle>
          <Card className="p-3">
            <ul className="divide-y divide-white/[.05]">
              {settlements.items.map((item) => (
                <li
                  key={item.id}
                  className={cn(
                    "flex flex-wrap items-center gap-3 px-2 py-3",
                    item.is_reversed && "opacity-45",
                  )}
                >
                  <Avatar name={item.from_name ?? "?"} id={item.from_user_id} size="sm" />
                  <span className="text-xs text-slate-300">{item.from_name}</span>
                  <ArrowRight size={12} className="text-slate-600" />
                  <Avatar name={item.to_name ?? "?"} id={item.to_user_id} size="sm" />
                  <span className="min-w-0 flex-1 truncate text-xs text-slate-300">
                    {item.to_name}
                    <span className="ml-2 text-[10px] text-slate-600">
                      {new Date(item.settlement_date).toLocaleDateString(undefined, {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                  </span>
                  <span
                    className={cn(
                      "tabular text-sm font-semibold text-white",
                      item.is_reversed && "line-through",
                    )}
                  >
                    {formatMoney(item.amount, currency)}
                  </span>
                  {!item.is_reversed &&
                  canWrite &&
                  (item.from_user_id === user?.id ||
                    item.to_user_id === user?.id ||
                    group?.role === "admin") ? (
                    <button
                      onClick={() => undo(item.id)}
                      aria-label="Reverse settlement"
                      className="rounded-lg p-1.5 text-slate-600 transition hover:bg-white/10 hover:text-debit"
                    >
                      <Undo2 size={13} />
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      ) : null}

      <RecordPaymentModal
        groupId={groupId}
        currency={currency}
        prefill={recording}
        open={!!recording || freeform}
        onClose={() => {
          setRecording(null);
          setFreeform(false);
        }}
      />
    </PageFade>
  );
}

function RecordPaymentModal({
  groupId,
  currency,
  prefill,
  open,
  onClose,
}: {
  groupId: number;
  currency: string;
  prefill: PairwiseDebt | null;
  open: boolean;
  onClose: () => void;
}) {
  const { user } = useAuth();
  const { data: members } = useMembers(groupId);
  const createSettlement = useCreateSettlement(groupId);
  const [error, setError] = useState<string | null>(null);

  const active = (members ?? []).filter((member) => member.status === "active");
  const [from, setFrom] = useState(prefill?.from_user_id ?? user?.id ?? 0);
  const [to, setTo] = useState(prefill?.to_user_id ?? 0);
  const [amount, setAmount] = useState(prefill?.amount ?? "");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");

  // Re-seed whenever a different row is picked.
  const seedKey = `${prefill?.from_user_id ?? "x"}-${prefill?.to_user_id ?? "x"}-${prefill?.amount ?? ""}`;
  const [lastSeed, setLastSeed] = useState(seedKey);
  if (seedKey !== lastSeed) {
    setLastSeed(seedKey);
    setFrom(prefill?.from_user_id ?? user?.id ?? 0);
    setTo(prefill?.to_user_id ?? 0);
    setAmount(prefill?.amount ?? "");
    setError(null);
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await createSettlement.mutateAsync({
        from_user_id: from,
        to_user_id: to,
        amount,
        settlement_date: date,
        notes: notes.trim() || null,
      });
      toast("Payment recorded.");
      onClose();
      setNotes("");
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Record a payment">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="from" className="label mb-1.5 block">
              From
            </label>
            <select
              id="from"
              className="input"
              value={from}
              onChange={(event) => setFrom(Number(event.target.value))}
            >
              <option value={0} className="bg-void-800">
                Select…
              </option>
              {active.map((member) => (
                <option key={member.user_id} value={member.user_id} className="bg-void-800">
                  {member.name}
                  {member.user_id === user?.id ? " (you)" : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="to" className="label mb-1.5 block">
              To
            </label>
            <select
              id="to"
              className="input"
              value={to}
              onChange={(event) => setTo(Number(event.target.value))}
            >
              <option value={0} className="bg-void-800">
                Select…
              </option>
              {active
                .filter((member) => member.user_id !== from)
                .map((member) => (
                  <option key={member.user_id} value={member.user_id} className="bg-void-800">
                    {member.name}
                    {member.user_id === user?.id ? " (you)" : ""}
                  </option>
                ))}
            </select>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="settle-amount" className="label mb-1.5 block">
              Amount
            </label>
            <input
              id="settle-amount"
              className="input tabular"
              inputMode="decimal"
              placeholder="0.00"
              value={amount}
              onChange={(event) => setAmount(event.target.value.replace(/[^\d.]/g, ""))}
              required
            />
          </div>
          <div>
            <label htmlFor="settle-date" className="label mb-1.5 block">
              Date
            </label>
            <input
              id="settle-date"
              type="date"
              className="input"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              required
            />
          </div>
        </div>

        <div>
          <label htmlFor="settle-notes" className="label mb-1.5 block">
            Notes (optional)
          </label>
          <input
            id="settle-notes"
            className="input"
            placeholder="UPI, cash, bank transfer…"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>

        <ErrorNote message={error} />

        <button
          type="submit"
          className="btn-primary w-full"
          disabled={!from || !to || from === to || !amount || createSettlement.isPending}
        >
          {createSettlement.isPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Handshake size={16} />
          )}
          Record {amount ? formatMoney(amount, currency) : "payment"}
        </button>
      </form>
    </Modal>
  );
}
