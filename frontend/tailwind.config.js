/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Near-black backdrop with a blue cast -- pure #000 makes neon look cheap.
        void: { 900: "#05050a", 800: "#080812", 700: "#0c0c18", 600: "#12121f" },
        neon: {
          cyan: "#22d3ee",
          violet: "#a855f7",
          pink: "#f472b6",
          lime: "#a3e635",
          amber: "#fbbf24",
        },
        // Money semantics: you are owed vs you owe.
        credit: "#34d399",
        debit: "#fb7185",
      },
      fontFamily: {
        sans: ["Outfit", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        "glow-cyan": "0 0 0 1px rgba(34,211,238,.35), 0 0 24px -4px rgba(34,211,238,.45)",
        "glow-violet": "0 0 0 1px rgba(168,85,247,.35), 0 0 24px -4px rgba(168,85,247,.45)",
        "glow-pink": "0 0 0 1px rgba(244,114,182,.35), 0 0 24px -4px rgba(244,114,182,.45)",
        "glow-credit": "0 0 0 1px rgba(52,211,153,.3), 0 0 22px -6px rgba(52,211,153,.5)",
        "glow-debit": "0 0 0 1px rgba(251,113,133,.3), 0 0 22px -6px rgba(251,113,133,.5)",
        card: "0 1px 0 0 rgba(255,255,255,.06) inset, 0 18px 40px -24px rgba(0,0,0,.9)",
      },
      keyframes: {
        drift: {
          "0%,100%": { transform: "translate3d(0,0,0) scale(1)" },
          "33%": { transform: "translate3d(4%,-6%,0) scale(1.08)" },
          "66%": { transform: "translate3d(-5%,4%,0) scale(.95)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(34,211,238,.45)" },
          "70%": { boxShadow: "0 0 0 12px rgba(34,211,238,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(34,211,238,0)" },
        },
        "scan-line": {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(400%)" },
        },
      },
      animation: {
        drift: "drift 24s ease-in-out infinite",
        "drift-slow": "drift 38s ease-in-out infinite reverse",
        shimmer: "shimmer 1.8s ease-in-out infinite",
        "pulse-ring": "pulse-ring 2.4s ease-out infinite",
        "scan-line": "scan-line 4s linear infinite",
      },
    },
  },
  plugins: [],
};
