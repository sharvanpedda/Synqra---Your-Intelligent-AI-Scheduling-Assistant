/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // night-shift control room base
        ink: "#07090F",      // deepest background
        ink2: "#0B0E14",     // section background
        panel: "#10151F",    // card surfaces
        panel2: "#171E2C",   // raised surfaces / hover
        line: "#1E2637",     // hairlines / rail ticks
        mist: "#8A93A6",     // secondary text
        signal: "#F2A65A",   // amber — "now", live/active state
        free: "#5FD4C0",     // teal — open/available time
        busy: "#E7E9EE",     // primary text / booked blocks
        alert: "#E0616B",    // conflicts / errors
        violet: "#8B7CF6",   // secondary accent (LLM/agent)
        google: "#4285F4",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        display: ["'Space Grotesk'", "Inter", "ui-sans-serif", "system-ui"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 40px -8px rgba(242,166,90,0.35)",
        glowTeal: "0 0 40px -8px rgba(95,212,192,0.35)",
        card: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 12px 32px -12px rgba(0,0,0,0.6)",
        float: "0 24px 60px -20px rgba(0,0,0,0.75)",
      },
      backgroundImage: {
        "grad-signal": "linear-gradient(120deg, #F2A65A 0%, #FFD9A0 45%, #5FD4C0 100%)",
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.45 },
        },
        slideUp: {
          "0%": { transform: "translateY(10px)", opacity: 0 },
          "100%": { transform: "translateY(0)", opacity: 1 },
        },
        fadeIn: {
          "0%": { opacity: 0 },
          "100%": { opacity: 1 },
        },
        scaleIn: {
          "0%": { transform: "scale(.96)", opacity: 0 },
          "100%": { transform: "scale(1)", opacity: 1 },
        },
        blink: { "0%,100%": { opacity: 1 }, "50%": { opacity: 0.15 } },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        floaty: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        typeDot: {
          "0%, 60%, 100%": { transform: "translateY(0)", opacity: 0.35 },
          "30%": { transform: "translateY(-4px)", opacity: 1 },
        },
        wave: {
          "0%, 100%": { transform: "scaleY(0.35)" },
          "50%": { transform: "scaleY(1)" },
        },
        pulseRing: {
          "0%": { transform: "scale(1)", opacity: 0.6 },
          "100%": { transform: "scale(2.2)", opacity: 0 },
        },
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        aurora: {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "33%": { transform: "translate(40px,-30px) scale(1.15)" },
          "66%": { transform: "translate(-30px,25px) scale(.95)" },
        },
        caret: {
          "0%,100%": { opacity: 1 },
          "50%": { opacity: 0 },
        },
        ping2: {
          "0%": { transform: "scale(1)", opacity: 0.8 },
          "75%,100%": { transform: "scale(2.4)", opacity: 0 },
        },
      },
      animation: {
        pulseSoft: "pulseSoft 2.2s ease-in-out infinite",
        slideUp: "slideUp .22s cubic-bezier(.22,.61,.36,1)",
        fadeIn: "fadeIn .3s ease-out",
        scaleIn: "scaleIn .18s cubic-bezier(.22,.61,.36,1)",
        blink: "blink 1.1s step-end infinite",
        floaty: "floaty 5s ease-in-out infinite",
        wave: "wave 1.1s ease-in-out infinite",
        pulseRing: "pulseRing 1.6s ease-out infinite",
        marquee: "marquee 28s linear infinite",
        aurora: "aurora 14s ease-in-out infinite",
        caret: "caret 1s step-end infinite",
        ping2: "ping2 1.8s cubic-bezier(0,0,.2,1) infinite",
      },
    },
  },
  plugins: [],
};
