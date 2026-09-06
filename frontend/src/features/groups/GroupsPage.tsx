import { motion } from "framer-motion";
import { ArrowRight, Loader2, LogIn, Plus, Users2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BalancePill,
  Card,
  EmptyState,
  ErrorNote,
  Modal,
  PageFade,
  Skeleton,
  Stagger,
  StaggerItem,
  toast,
} from "../../components/ui";
import { toApiError } from "../../lib/api";
import { useCreateGroup, useGroups, useJoinGroup } from "../../lib/queries";
import { useAuth } from "../auth/AuthContext";

const CURRENCIES = ["INR", "USD", "EUR", "GBP", "AUD", "CAD", "SGD", "AED"];

export default function GroupsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: groups, isLoading } = useGroups();
  const [creating, setCreating] = useState(false);
  const [joining, setJoining] = useState(false);

  return (
    <PageFade>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label mb-1">Signed in as {user?.name}</p>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Your groups
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setJoining(true)} className="btn-ghost">
            <LogIn size={15} /> Join with code
          </button>
          <button onClick={() => setCreating(true)} className="btn-primary">
            <Plus size={16} /> New group
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((n) => (
            <Skeleton key={n} className="h-40" />
          ))}
        </div>
      ) : !groups?.length ? (
        <EmptyState
          icon={<Users2 size={22} />}
          title="No groups yet"
          description="Create one for your flat, a trip or a shared tab — then invite everyone with a code."
          action={
            <button onClick={() => setCreating(true)} className="btn-primary">
              <Plus size={16} /> Create your first group
            </button>
          }
        />
      ) : (
        <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((group) => (
            <StaggerItem key={group.id}>
              <motion.div whileHover={{ y: -4 }} whileTap={{ scale: 0.985 }}>
                <Card
                  interactive
                  glow="violet"
                  onClick={() => navigate(`/groups/${group.id}/dashboard`)}
                  className="group relative h-full overflow-hidden"
                >
                  <span className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon-violet/50 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate text-base font-semibold text-white">
                        {group.name}
                      </h3>
                      <p className="mt-1 text-xs text-slate-500">
                        {group.member_count ?? 0} member
                        {group.member_count === 1 ? "" : "s"} · {group.currency}
                        {group.is_archived ? " · archived" : ""}
                      </p>
                    </div>
                    <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      {group.role}
                    </span>
                  </div>

                  <div className="mt-6 flex items-end justify-between gap-3">
                    <div>
                      <p className="label mb-1.5">Your balance</p>
                      <BalancePill
                        value={group.my_balance ?? "0.00"}
                        currency={group.currency}
                      />
                    </div>
                    <ArrowRight
                      size={18}
                      className="mb-1 text-slate-600 transition-all group-hover:translate-x-1 group-hover:text-neon-violet"
                    />
                  </div>
                </Card>
              </motion.div>
            </StaggerItem>
          ))}
        </Stagger>
      )}

      <CreateGroupModal open={creating} onClose={() => setCreating(false)} />
      <JoinGroupModal open={joining} onClose={() => setJoining(false)} />
    </PageFade>
  );
}

function CreateGroupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const createGroup = useCreateGroup();

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const group = await createGroup.mutateAsync({ name: name.trim(), currency });
      toast(`${group.name} is ready.`);
      onClose();
      setName("");
      navigate(`/groups/${group.id}/dashboard`);
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New group">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="group-name" className="label mb-1.5 block">
            Group name
          </label>
          <input
            id="group-name"
            className="input"
            placeholder="Flat 3B"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
            required
          />
        </div>
        <div>
          <label htmlFor="group-currency" className="label mb-1.5 block">
            Currency
          </label>
          <select
            id="group-currency"
            className="input"
            value={currency}
            onChange={(event) => setCurrency(event.target.value)}
          >
            {CURRENCIES.map((code) => (
              <option key={code} value={code} className="bg-void-800">
                {code}
              </option>
            ))}
          </select>
        </div>
        <ErrorNote message={error} />
        <button
          type="submit"
          className="btn-primary w-full"
          disabled={!name.trim() || createGroup.isPending}
        >
          {createGroup.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
          Create group
        </button>
      </form>
    </Modal>
  );
}

function JoinGroupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const joinGroup = useJoinGroup();

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const group = await joinGroup.mutateAsync(code.trim().toUpperCase());
      toast(`Joined ${group.name}.`);
      onClose();
      setCode("");
      navigate(`/groups/${group.id}/dashboard`);
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Join a group">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="invite-code" className="label mb-1.5 block">
            Invite code
          </label>
          <input
            id="invite-code"
            className="input text-center text-lg font-semibold uppercase tracking-[0.4em]"
            placeholder="ABCD2345"
            maxLength={8}
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            autoFocus
            required
          />
          <p className="mt-2 text-xs text-slate-500">
            Ask a group admin for the code. Codes expire after a week.
          </p>
        </div>
        <ErrorNote message={error} />
        <button
          type="submit"
          className="btn-primary w-full"
          disabled={code.length < 4 || joinGroup.isPending}
        >
          {joinGroup.isPending ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
          Join group
        </button>
      </form>
    </Modal>
  );
}
