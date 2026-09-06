import { motion } from "framer-motion";
import { Waves } from "lucide-react";
import { Link } from "react-router-dom";

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <motion.div
        initial={{ opacity: 0, y: 22, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-md"
      >
        <div className="mb-7 flex flex-col items-center text-center">
          <motion.span
            whileHover={{ rotate: -8, scale: 1.06 }}
            className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-cyan-300 to-violet-500 text-void-900 shadow-glow-cyan"
          >
            <Waves size={26} strokeWidth={2.5} />
          </motion.span>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">{title}</h1>
          <p className="mt-2 max-w-xs text-sm leading-relaxed text-slate-500">{subtitle}</p>
        </div>

        <div className="glass relative overflow-hidden p-6 sm:p-7">
          {/* Thin neon rule along the top edge of the card. */}
          <span className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon-cyan/60 to-transparent" />
          {children}
        </div>

        <p className="mt-5 text-center text-xs text-slate-500">{footer}</p>
      </motion.div>
    </div>
  );
}

export function AuthLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link to={to} className="font-semibold text-neon-cyan transition hover:text-cyan-200">
      {children}
    </Link>
  );
}
