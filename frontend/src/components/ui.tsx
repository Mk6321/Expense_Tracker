import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { d, formatMoney, isNegative, isZero } from "../lib/money";

export function cn(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

/* ------------------------------------------------------------------ backdrop */

/**
 * Two slow-drifting colour blobs behind the whole app. Fixed and pointer-events
 * none, so it never interferes with anything on top of it.
 */
export function Aurora() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="animate-drift absolute -left-40 -top-40 h-[34rem] w-[34rem] rounded-full bg-neon-violet/20 blur-[120px]" />
      <div className="animate-drift-slow absolute -right-32 top-1/4 h-[30rem] w-[30rem] rounded-full bg-neon-cyan/20 blur-[120px]" />
      <div className="animate-drift absolute bottom-[-12rem] left-1/3 h-[26rem] w-[26rem] rounded-full bg-neon-pink/10 blur-[130px]" />
      {/* Faint grid, to give the dark ground some structure. */}
      <div
        className="absolute inset-0 opacity-[0.18]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage: "radial-gradient(ellipse 80% 60% at 50% 0%, black, transparent 75%)",
        }}
      />
    </div>
  );
}

/* --------------------------------------------------------------------- cards */

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glow?: "cyan" | "violet" | "pink" | "none";
  interactive?: boolean;
}

export function Card({ glow = "none", interactive, className, children, ...rest }: CardProps) {
  const glowClass =
    glow === "cyan"
      ? "hover:shadow-glow-cyan"
      : glow === "violet"
        ? "hover:shadow-glow-violet"
        : glow === "pink"
          ? "hover:shadow-glow-pink"
          : "";
  return (
    <div
      className={cn(
        "glass p-5",
        interactive && "glass-hover cursor-pointer",
        interactive && glowClass,
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  children,
  action,
}: {
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <h2 className="text-sm font-semibold tracking-wide text-slate-300">{children}</h2>
      {action}
    </div>
  );
}

/* --------------------------------------------------------------------- money */

/**
 * Money that counts up to its value when it changes. Purely presentational: the
 * spring drives a display number, while the exact string still comes from the API.
 */
export function AnimatedMoney({
  value,
  currency = "INR",
  className,
  signed,
  absolute,
}: {
  value: string;
  currency?: string;
  className?: string;
  signed?: boolean;
  absolute?: boolean;
}) {
  const target = d(value).toNumber();
  const motionValue = useMotionValue(target);
  const spring = useSpring(motionValue, { stiffness: 90, damping: 18, mass: 0.6 });
  const text = useTransform(spring, (latest) =>
    formatMoney(latest.toFixed(2), currency, { signed, absolute }),
  );

  useEffect(() => {
    motionValue.set(target);
  }, [target, motionValue]);

  return <motion.span className={cn("tabular", className)}>{text}</motion.span>;
}

/** Green when you are owed, red when you owe, grey at zero. */
export function balanceTone(value: string) {
  if (isZero(value)) return "text-slate-400";
  return isNegative(value) ? "text-debit" : "text-credit";
}

export function BalancePill({ value, currency }: { value: string; currency: string }) {
  const zero = isZero(value);
  const negative = isNegative(value);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
        zero
          ? "border-white/10 bg-white/5 text-slate-400"
          : negative
            ? "border-debit/30 bg-debit/10 text-debit"
            : "border-credit/30 bg-credit/10 text-credit",
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", zero ? "bg-slate-500" : negative ? "bg-debit" : "bg-credit")} />
      <span className="tabular">{formatMoney(value, currency, { absolute: true })}</span>
    </span>
  );
}

/* ------------------------------------------------------------------- avatars */

const AVATAR_GRADIENTS = [
  "from-cyan-400 to-blue-500",
  "from-violet-400 to-fuchsia-500",
  "from-pink-400 to-rose-500",
  "from-lime-400 to-emerald-500",
  "from-amber-400 to-orange-500",
  "from-sky-400 to-indigo-500",
];

export function Avatar({
  name,
  size = "md",
  id = 0,
}: {
  name: string;
  size?: "sm" | "md" | "lg";
  id?: number;
}) {
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  const dimensions =
    size === "sm" ? "h-7 w-7 text-[10px]" : size === "lg" ? "h-12 w-12 text-sm" : "h-9 w-9 text-xs";

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br font-bold text-void-900 ring-1 ring-white/20",
        AVATAR_GRADIENTS[Math.abs(id) % AVATAR_GRADIENTS.length],
        dimensions,
      )}
      title={name}
    >
      {initials || "?"}
    </span>
  );
}

/* -------------------------------------------------------------------- states */

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("shimmer relative overflow-hidden rounded-xl bg-white/[.05]", className)} />
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 px-6 py-14 text-center"
    >
      {icon ? (
        <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/[.04] text-neon-cyan">
          {icon}
        </div>
      ) : null}
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      {description ? (
        <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-slate-500">{description}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </motion.div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  return (
    <AnimatePresence>
      {message ? (
        <motion.p
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          role="alert"
          className="overflow-hidden rounded-xl border border-debit/25 bg-debit/10 px-3 py-2 text-xs text-debit"
        >
          {message}
        </motion.p>
      ) : null}
    </AnimatePresence>
  );
}

/* --------------------------------------------------------------------- modal */

export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-void-900/80 backdrop-blur-sm"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            // Slides up from the bottom on phones, springs in on desktop.
            initial={{ opacity: 0, y: 40, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 320, damping: 30 }}
            className={cn(
              "glass relative z-10 max-h-[92vh] w-full overflow-y-auto rounded-b-none rounded-t-3xl p-5 sm:rounded-3xl",
              wide ? "sm:max-w-2xl" : "sm:max-w-md",
            )}
          >
            <div className="mb-4 flex items-center justify-between gap-4">
              <h3 className="text-base font-semibold text-white">{title}</h3>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-1.5 text-slate-500 transition hover:bg-white/10 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>
  );
}

/* -------------------------------------------------------------------- toasts */

type Toast = { id: number; message: string; tone: "ok" | "bad" };
let pushToast: ((message: string, tone?: "ok" | "bad") => void) | null = null;

export function toast(message: string, tone: "ok" | "bad" = "ok") {
  pushToast?.(message, tone);
}

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  useEffect(() => {
    pushToast = (message, tone = "ok") => {
      const id = nextId.current++;
      setToasts((current) => [...current, { id, message, tone }]);
      setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 4000);
    };
    return () => {
      pushToast = null;
    };
  }, []);

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 sm:bottom-6">
      <AnimatePresence>
        {toasts.map((item) => (
          <motion.div
            key={item.id}
            layout
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            className={cn(
              "glass pointer-events-auto max-w-sm px-4 py-2.5 text-sm",
              item.tone === "ok" ? "shadow-glow-credit" : "shadow-glow-debit",
            )}
          >
            {item.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ controls */

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex gap-1 rounded-xl border border-white/10 bg-void-800/60 p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            "relative flex-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
            value === option.value ? "text-void-900" : "text-slate-400 hover:text-white",
          )}
        >
          {value === option.value ? (
            // Shared layoutId makes the pill glide between options.
            <motion.span
              layoutId="segmented-pill"
              transition={{ type: "spring", stiffness: 420, damping: 34 }}
              className="absolute inset-0 rounded-lg bg-gradient-to-r from-cyan-300 to-violet-400"
            />
          ) : null}
          <span className="relative z-10">{option.label}</span>
        </button>
      ))}
    </div>
  );
}

/** Horizontal meter used in the reports view. */
export function Meter({ percent, tone = "cyan" }: { percent: number; tone?: "cyan" | "violet" }) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[.06]">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%` }}
        transition={{ type: "spring", stiffness: 60, damping: 18 }}
        className={cn(
          "h-full rounded-full",
          tone === "cyan"
            ? "bg-gradient-to-r from-cyan-400 to-sky-400"
            : "bg-gradient-to-r from-violet-400 to-fuchsia-400",
        )}
      />
    </div>
  );
}

/* ----------------------------------------------------------- page transition */

export function PageFade({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

/** Staggers direct children in on mount. */
export function Stagger({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 12 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } },
      }}
    >
      {children}
    </motion.div>
  );
}
