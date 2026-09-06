import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Waves } from "lucide-react";

/**
 * Shown while the session is being restored. Render's free tier cold-starts for
 * 30-50s, so after a few seconds this stops looking like a hung spinner and says
 * what is actually happening (Section 15).
 */
export function BootSplash() {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 3500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6">
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 16 }}
        className="animate-pulse-ring grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-cyan-300 to-violet-500 text-void-900"
      >
        <Waves size={28} strokeWidth={2.5} />
      </motion.div>

      <div className="h-1 w-48 overflow-hidden rounded-full bg-white/[.06]">
        <motion.div
          className="h-full w-1/3 rounded-full bg-gradient-to-r from-cyan-300 to-violet-400"
          animate={{ x: ["-100%", "300%"] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="max-w-xs text-center text-xs leading-relaxed text-slate-500"
      >
        {slow
          ? "Waking up the server… free-tier instances sleep after a while, so the first request can take up to a minute."
          : "Restoring your session…"}
      </motion.p>
    </div>
  );
}
