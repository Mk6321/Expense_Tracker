import { motion } from "framer-motion";
import { Check, Copy, Loader2, Tag, UserMinus, UserPlus } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  Avatar,
  BalancePill,
  Card,
  ErrorNote,
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
import { formatMoney, isZero } from "../../lib/money";
import {
  useBalances,
  useCategories,
  useChangeRole,
  useCreateCategory,
  useCreateInvite,
  useGroup,
  useMembers,
  useRemoveMember,
} from "../../lib/queries";
import type { Member, Role } from "../../types/api";
import { useAuth } from "../auth/AuthContext";

const ROLES: Role[] = ["admin", "member", "viewer"];

const ROLE_HELP: Record<Role, string> = {
  admin: "Manages the group, members and categories, and can edit any expense.",
  member: "Adds expenses, records settlements, edits only what they created.",
  viewer: "Read-only. Sees balances and reports but cannot change anything.",
};

export default function MembersPage() {
  const groupId = Number(useParams().groupId);
  const { user } = useAuth();
  const { data: group } = useGroup(groupId);
  const { data: members, isLoading } = useMembers(groupId);
  const { data: balances } = useBalances(groupId);
  const changeRole = useChangeRole(groupId);
  const [removing, setRemoving] = useState<Member | null>(null);
  const [inviting, setInviting] = useState(false);
  const [addingCategory, setAddingCategory] = useState(false);

  const currency = group?.currency ?? "INR";
  const isAdmin = group?.role === "admin";

  const balanceOf = (userId: number) =>
    balances?.balances.find((entry) => entry.user_id === userId)?.balance ?? "0.00";

  const updateRole = async (userId: number, role: Role) => {
    try {
      await changeRole.mutateAsync({ userId, role });
      toast("Role updated.");
    } catch (caught) {
      toast(toApiError(caught).message, "bad");
    }
  };

  return (
    <PageFade>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label mb-1">{group?.name}</p>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Members</h1>
        </div>
        {isAdmin ? (
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setAddingCategory(true)} className="btn-ghost">
              <Tag size={15} /> Categories
            </button>
            <button onClick={() => setInviting(true)} className="btn-primary">
              <UserPlus size={16} /> Invite
            </button>
          </div>
        ) : null}
      </div>

      {isLoading ? (
        <div className="space-y-2.5">
          {[0, 1, 2].map((n) => (
            <Skeleton key={n} className="h-20" />
          ))}
        </div>
      ) : (
        <Stagger className="space-y-2.5">
          {(members ?? []).map((member) => {
            const removed = member.status === "removed";
            const isMe = member.user_id === user?.id;
            return (
              <StaggerItem key={member.user_id}>
                <Card className={cn("flex flex-wrap items-center gap-4", removed && "opacity-50")}>
                  <Avatar name={member.name} id={member.user_id} size="lg" />

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-white">
                      {member.name}
                      {isMe ? <span className="ml-1.5 text-xs text-slate-500">(you)</span> : null}
                      {removed ? (
                        <span className="ml-2 rounded-md border border-white/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-slate-500">
                          removed
                        </span>
                      ) : null}
                    </p>
                    <p className="truncate text-xs text-slate-500">{member.email}</p>
                    <p className="mt-1 text-[11px] text-slate-600">
                      Joined{" "}
                      {new Date(member.joined_at).toLocaleDateString(undefined, {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </p>
                  </div>

                  <BalancePill value={balanceOf(member.user_id)} currency={currency} />

                  {isAdmin && !removed ? (
                    <div className="flex items-center gap-2">
                      <select
                        aria-label={`Role for ${member.name}`}
                        className="input w-28 py-1.5 text-xs"
                        value={member.role}
                        onChange={(event) =>
                          updateRole(member.user_id, event.target.value as Role)
                        }
                      >
                        {ROLES.map((role) => (
                          <option key={role} value={role} className="bg-void-800">
                            {role}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => setRemoving(member)}
                        aria-label={`Remove ${member.name}`}
                        className="rounded-lg p-2 text-slate-600 transition hover:bg-white/10 hover:text-debit"
                      >
                        <UserMinus size={15} />
                      </button>
                    </div>
                  ) : (
                    <span className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      {member.role}
                    </span>
                  )}
                </Card>
              </StaggerItem>
            );
          })}
        </Stagger>
      )}

      <div className="mt-8">
        <SectionTitle>What each role can do</SectionTitle>
        <Card className="space-y-3">
          {ROLES.map((role) => (
            <div key={role} className="flex gap-3">
              <span className="mt-0.5 w-16 shrink-0 text-[11px] font-semibold uppercase tracking-wider text-neon-cyan">
                {role}
              </span>
              <p className="text-xs leading-relaxed text-slate-500">{ROLE_HELP[role]}</p>
            </div>
          ))}
        </Card>
      </div>

      <InviteModal groupId={groupId} open={inviting} onClose={() => setInviting(false)} />
      <CategoryModal
        groupId={groupId}
        open={addingCategory}
        onClose={() => setAddingCategory(false)}
      />
      <RemoveMemberModal
        groupId={groupId}
        currency={currency}
        member={removing}
        balance={removing ? balanceOf(removing.user_id) : "0.00"}
        onClose={() => setRemoving(null)}
      />
    </PageFade>
  );
}

function InviteModal({
  groupId,
  open,
  onClose,
}: {
  groupId: number;
  open: boolean;
  onClose: () => void;
}) {
  const createInvite = useCreateInvite(groupId);
  const [code, setCode] = useState<string | null>(null);
  const [expires, setExpires] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setError(null);
    try {
      const invite = await createInvite.mutateAsync();
      setCode(invite.code);
      setExpires(invite.expires_at);
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  };

  const copy = async () => {
    if (!code) return;
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal open={open} onClose={onClose} title="Invite someone">
      <div className="space-y-4">
        <p className="text-sm leading-relaxed text-slate-400">
          Share this code. They enter it under <em>Join with code</em> on their groups page.
        </p>

        {code ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-2xl border border-neon-cyan/25 bg-neon-cyan/[.06] p-5 text-center shadow-glow-cyan"
          >
            <p className="neon-text-cyan font-mono text-3xl font-bold tracking-[0.35em]">
              {code}
            </p>
            <p className="mt-3 text-[11px] text-slate-500">
              Expires{" "}
              {expires
                ? new Date(expires).toLocaleDateString(undefined, {
                    day: "numeric",
                    month: "long",
                  })
                : "in 7 days"}
            </p>
            <button onClick={copy} className="btn-ghost mt-4">
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy code"}
            </button>
          </motion.div>
        ) : null}

        <ErrorNote message={error} />

        <button onClick={generate} className="btn-primary w-full" disabled={createInvite.isPending}>
          {createInvite.isPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <UserPlus size={16} />
          )}
          {code ? "Generate another code" : "Generate invite code"}
        </button>
      </div>
    </Modal>
  );
}

function CategoryModal({
  groupId,
  open,
  onClose,
}: {
  groupId: number;
  open: boolean;
  onClose: () => void;
}) {
  const { data: categories } = useCategories(groupId);
  const createCategory = useCreateCategory(groupId);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await createCategory.mutateAsync({ name: name.trim() });
      setName("");
      toast("Category added.");
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Categories">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-1.5">
          {(categories ?? []).map((category) => (
            <span
              key={category.id}
              className={cn(
                "rounded-lg border px-2.5 py-1 text-xs",
                category.group_id
                  ? "border-neon-violet/30 bg-neon-violet/10 text-violet-200"
                  : "border-white/10 bg-white/5 text-slate-400",
              )}
            >
              {category.name}
            </span>
          ))}
        </div>
        <p className="text-[11px] text-slate-600">
          Grey ones are shared defaults. Purple ones belong to this group.
        </p>

        <form onSubmit={submit} className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="New category name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <button
            type="submit"
            className="btn-primary shrink-0"
            disabled={!name.trim() || createCategory.isPending}
          >
            {createCategory.isPending ? <Loader2 size={15} className="animate-spin" /> : "Add"}
          </button>
        </form>
        <ErrorNote message={error} />
      </div>
    </Modal>
  );
}

function RemoveMemberModal({
  groupId,
  currency,
  member,
  balance,
  onClose,
}: {
  groupId: number;
  currency: string;
  member: Member | null;
  balance: string;
  onClose: () => void;
}) {
  const removeMember = useRemoveMember(groupId);
  const [error, setError] = useState<string | null>(null);
  const settled = isZero(balance);

  const remove = async (force: boolean) => {
    if (!member) return;
    setError(null);
    try {
      await removeMember.mutateAsync({ userId: member.user_id, force });
      toast(`${member.name} was removed.`);
      onClose();
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  };

  return (
    <Modal open={!!member} onClose={onClose} title={`Remove ${member?.name ?? ""}?`}>
      <div className="space-y-4">
        <p className="text-sm leading-relaxed text-slate-400">
          They lose access to this group. Their past expenses and splits stay exactly as they
          are, so nobody's history changes.
        </p>

        {!settled ? (
          <div className="rounded-xl border border-neon-amber/25 bg-neon-amber/[.07] px-3.5 py-3 text-xs leading-relaxed text-neon-amber">
            They still have an outstanding balance of{" "}
            <span className="tabular font-semibold">
              {formatMoney(balance, currency, { absolute: true })}
            </span>
            . Settling up first keeps the ledger clean — forcing the removal leaves that debt
            sitting in the group's history.
          </div>
        ) : null}

        <ErrorNote message={error} />

        <div className="flex flex-wrap gap-2">
          <button onClick={onClose} className="btn-ghost flex-1">
            Cancel
          </button>
          <button
            onClick={() => remove(!settled)}
            disabled={removeMember.isPending}
            className="btn-danger flex-1"
          >
            {removeMember.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <UserMinus size={15} />
            )}
            {settled ? "Remove" : "Force remove"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
