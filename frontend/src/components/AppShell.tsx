import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeftRight,
  BarChart3,
  LayoutDashboard,
  LogOut,
  Receipt,
  Users,
  Waves,
} from "lucide-react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { useGroup } from "../lib/queries";
import { Avatar, BalancePill, cn } from "./ui";

const NAV = [
  { to: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "expenses", label: "Expenses", icon: Receipt },
  { to: "settle", label: "Settle up", icon: ArrowLeftRight },
  { to: "reports", label: "Reports", icon: BarChart3 },
  { to: "members", label: "Members", icon: Users },
];

function useGroupId(): number {
  const { groupId } = useParams();
  return Number(groupId ?? 0);
}

/**
 * Sidebar on desktop, bottom tab bar on phones. The group lives in the URL, so a
 * refresh or a shared deep link lands in the right place (Section 11).
 */
export function AppShell() {
  const groupId = useGroupId();
  const { data: group } = useGroup(groupId);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const inGroup = groupId > 0;

  const signOut = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* ------------------------------------------------- desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-white/[.06] bg-void-800/40 px-4 py-6 backdrop-blur-xl lg:flex">
        <button
          onClick={() => navigate("/groups")}
          className="mb-8 flex items-center gap-2.5 px-2 text-left"
        >
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-cyan-300 to-violet-500 text-void-900">
            <Waves size={18} strokeWidth={2.5} />
          </span>
          <span className="text-lg font-bold tracking-tight text-white">Splitwave</span>
        </button>

        {inGroup ? (
          <>
            <div className="mb-4 rounded-2xl border border-white/[.07] bg-white/[.03] p-3.5">
              <p className="label mb-1">Current group</p>
              <p className="truncate text-sm font-semibold text-white">
                {group?.name ?? "…"}
              </p>
              {group ? (
                <div className="mt-2.5">
                  <BalancePill value={group.my_balance ?? "0.00"} currency={group.currency} />
                </div>
              ) : null}
            </div>

            <nav className="flex flex-col gap-1">
              {NAV.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={`/groups/${groupId}/${to}`}>
                  {({ isActive }) => (
                    <span
                      className={cn(
                        "relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                        isActive ? "text-white" : "text-slate-400 hover:text-white",
                      )}
                    >
                      {isActive ? (
                        <motion.span
                          layoutId="nav-active"
                          transition={{ type: "spring", stiffness: 380, damping: 32 }}
                          className="absolute inset-0 rounded-xl border border-neon-cyan/25 bg-neon-cyan/[.08] shadow-glow-cyan"
                        />
                      ) : null}
                      <Icon size={17} className="relative z-10" />
                      <span className="relative z-10">{label}</span>
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
          </>
        ) : (
          <p className="px-2 text-xs leading-relaxed text-slate-500">
            Pick a group to see its dashboard, expenses and balances.
          </p>
        )}

        <div className="mt-auto flex items-center gap-3 rounded-2xl border border-white/[.07] bg-white/[.03] p-3">
          <Avatar name={user?.name ?? "?"} id={user?.id} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">{user?.name}</p>
            <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
          </div>
          <button
            onClick={signOut}
            aria-label="Sign out"
            className="rounded-lg p-2 text-slate-500 transition hover:bg-white/10 hover:text-debit"
          >
            <LogOut size={15} />
          </button>
        </div>
      </aside>

      {/* ----------------------------------------------------- mobile header */}
      <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-white/[.06] bg-void-900/85 px-4 py-3 backdrop-blur-xl lg:hidden">
        <button onClick={() => navigate("/groups")} className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-cyan-300 to-violet-500 text-void-900">
            <Waves size={16} strokeWidth={2.5} />
          </span>
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-white">
            {inGroup ? (group?.name ?? "…") : "Your groups"}
          </p>
          {inGroup && group ? (
            <p className="truncate text-[11px] text-slate-500">
              {group.member_count} members · {group.currency}
            </p>
          ) : null}
        </div>
        {inGroup && group ? (
          <BalancePill value={group.my_balance ?? "0.00"} currency={group.currency} />
        ) : (
          <button
            onClick={signOut}
            aria-label="Sign out"
            className="rounded-lg p-2 text-slate-500 transition hover:text-debit"
          >
            <LogOut size={16} />
          </button>
        )}
      </header>

      {/* ------------------------------------------------------------- main */}
      <main className="flex-1 px-4 pb-28 pt-5 sm:px-6 lg:px-10 lg:pb-12 lg:pt-8">
        <div className="mx-auto w-full max-w-6xl">
          <Outlet />
        </div>
      </main>

      {/* ------------------------------------------------- mobile bottom nav */}
      <AnimatePresence>
        {inGroup ? (
          <motion.nav
            initial={{ y: 80 }}
            animate={{ y: 0 }}
            exit={{ y: 80 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed inset-x-0 bottom-0 z-40 border-t border-white/[.07] bg-void-900/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
          >
            <div className="flex items-stretch justify-around px-1 py-1.5">
              {NAV.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={`/groups/${groupId}/${to}`} className="flex-1">
                  {({ isActive }) => (
                    <span
                      className={cn(
                        "relative flex flex-col items-center gap-1 rounded-xl px-1 py-2 text-[10px] font-medium transition-colors",
                        isActive ? "text-neon-cyan" : "text-slate-500",
                      )}
                    >
                      {isActive ? (
                        <motion.span
                          layoutId="mobile-nav-active"
                          transition={{ type: "spring", stiffness: 400, damping: 34 }}
                          className="absolute inset-x-2 -top-1.5 h-0.5 rounded-full bg-neon-cyan shadow-glow-cyan"
                        />
                      ) : null}
                      <Icon size={19} />
                      {label}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          </motion.nav>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
