import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import DayRail from "../components/DayRail";
import LoginScreen from "../components/LoginScreen";
import HeroDemo from "../components/HeroDemo";
import Brand from "../components/Brand";

export default function Home() {
  const { user } = useAuth();
  const [loginOpen, setLoginOpen] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="app-bg">
      {/* top nav — stays put while scrolling */}
      <header className="sticky top-0 z-50 border-b border-line/70 bg-ink/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Brand size="lg" />
          <div className="flex items-center gap-3">
            <button onClick={() => setLoginOpen(true)} className="btn-primary text-sm">
              Get started
            </button>
            <button
              onClick={() => setLoginOpen(true)}
              className="rounded-lg border border-line px-4 py-2 text-sm text-mist transition-colors hover:border-signal/50 hover:text-busy"
            >
              Log in with Google
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6">
        {/* ================= HERO ================= */}
        <section className="relative grid items-center gap-14 py-16 md:grid-cols-2 lg:py-24">
          {/* aurora blobs */}
          <div className="pointer-events-none absolute inset-0 -z-10">
            <div className="absolute -top-24 -left-24 h-80 w-80 rounded-full bg-signal/10 blur-[100px] animate-aurora" />
            <div className="absolute top-10 right-0 h-72 w-72 rounded-full bg-free/10 blur-[100px] animate-aurora [animation-delay:3s]" />
            <div className="absolute bottom-0 left-1/3 h-64 w-64 rounded-full bg-violet/10 blur-[100px] animate-aurora [animation-delay:6s]" />
          </div>

          <div>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-signal/30 bg-signal/5 px-3 py-1 font-mono text-[11px] text-signal">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping2 rounded-full bg-signal" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-signal" />
              </span>
              AGENTIC RAG · LANGGRAPH · VOICE-FIRST
            </div>

            <h1 className="font-display text-5xl font-bold leading-[1.05] tracking-tight text-busy lg:text-6xl">
              A schedule assistant that reads your day,{" "}
              <span className="grad-text">then acts on it.</span>
            </h1>

            <p className="mt-6 max-w-xl text-lg leading-relaxed text-mist">
              Ask it out loud or type it in — "am I free Friday afternoon?", "move my 2 PM to 4",
              "when's my dentist thing?". It searches the next 30 days with RAG, catches conflicts
              before they happen, and <span className="text-busy">speaks the answer back</span>.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button onClick={() => setLoginOpen(true)} className="btn-primary text-base">
                Get started →
              </button>
              <button onClick={() => setLoginOpen(true)} className="btn-ghost">
                Log in with Google
              </button>
            </div>

            <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-xs text-mist/80">
              <span className="flex items-center gap-1.5">
                <Check /> synced to your real Google Calendar
              </span>
              <span className="flex items-center gap-1.5">
                <Check /> type or talk to it
              </span>
              <span className="flex items-center gap-1.5">
                <Check /> catches conflicts before they happen
              </span>
            </div>
          </div>

          {/* interactive product preview */}
          <div className="relative">
            <div className="absolute -inset-6 -z-10 rounded-3xl bg-gradient-to-br from-signal/20 via-transparent to-free/20 blur-2xl" />
            <HeroDemo />
          </div>
        </section>

        {/* ================= STATS ================= */}
        <section className="grid grid-cols-3 gap-px overflow-hidden rounded-2xl border border-line bg-line">
          <Stat value="30" label="days out it plans and searches across" />
          <Stat value="4" label="event types · meeting to errand" />
          <Stat value="2" label="tools · get & update, conflict-checked" />
        </section>

        {/* ================= SIGNATURE DAY RAIL ================= */}
        <section className="mt-20">
          <div className="mb-6 flex items-end justify-between">
            <div>
              <h2 className="font-display text-2xl font-semibold text-busy">
                The whole day on one line
              </h2>
              <p className="mt-1 text-sm text-mist">
                Booked blocks, live "now" marker, and free space — the signature timeline.
              </p>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-widest text-mist">
              24-hour rail
            </span>
          </div>
          <div className="card p-6">
            <DayRail
              events={[
                { id: "a", title: "Team Sync", event_date: "2026-08-11", start_time: "09:00", end_time: "10:00", category: "meeting", source: "local" },
                { id: "b", title: "React Workshop", event_date: "2026-08-11", start_time: "11:00", end_time: "12:30", category: "workshop", source: "local" },
                { id: "c", title: "Dentist", event_date: "2026-08-11", start_time: "13:00", end_time: "14:00", category: "appointment", source: "local" },
                { id: "d", title: "Client Call", event_date: "2026-08-11", start_time: "14:30", end_time: "15:30", category: "meeting", source: "local" },
              ]}
              height={72}
            />
          </div>
        </section>

        {/* ================= FEATURES ================= */}
        <section className="mt-20 grid gap-5 md:grid-cols-3">
          <Feature
            icon="✦"
            tone="text-signal"
            title="Grounded in RAG"
            body="Every answer is retrieved from your actual events — exact date lookups plus semantic search over embeddings, so 'the dentist thing' just works."
          />
          <Feature
            icon="⌁"
            tone="text-free"
            title="Speak, and it speaks back"
            body="Microphone in, voice out — the same agent transcribes and replies by voice, no browser-specific speech support required."
          />
          <Feature
            icon="! "
            tone="text-alert"
            title="Never double-books"
            body="Every add or move runs a live conflict check first. The agent can move, reschedule, and delete events by plain language — and it asks before guessing."
          />
        </section>

        {/* ================= STACK ================= */}
        <section className="mt-20 pb-20">
          <div className="rounded-2xl border border-line bg-panel/50 p-8 text-center">
            <h2 className="font-display text-xl font-semibold text-busy">
              What's actually running under the hood
            </h2>
            <p className="mx-auto mt-2 max-w-2xl text-sm text-mist">
              LangGraph routes intent → resolves dates → retrieves (RAG) → decides → calls tools.
              ChromaDB stores local ONNX embeddings. Sarvam AI handles speech in and out.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2.5">
              {["LangGraph", "ChromaDB", "ONNX MiniLM", "Sarvam AI voice", "FastAPI", "Google Calendar API", "React + Vite", "SSE alerts"].map((t) => (
                <span key={t} className="chip text-mist hover:border-signal/50 hover:text-signal transition-colors">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* footer */}
      <footer className="border-t border-line/60">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-6 text-xs text-mist">
          <span>Synqra · agentic RAG, voice-first</span>
          <span className="font-mono">FastAPI · LangGraph · ChromaDB</span>
        </div>
      </footer>

      {loginOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4 backdrop-blur-sm animate-fadeIn"
          onClick={() => setLoginOpen(false)}
        >
          <div className="w-full max-w-md animate-scaleIn" onClick={(e) => e.stopPropagation()}>
            <LoginScreen />
          </div>
        </div>
      )}
    </div>
  );
}

function Check() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#5FD4C0" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-ink px-6 py-7 text-center">
      <div className="font-display text-4xl font-bold grad-text">{value}</div>
      <div className="mt-1.5 text-xs text-mist">{label}</div>
    </div>
  );
}

function Feature({
  icon,
  tone,
  title,
  body,
}: {
  icon: string;
  tone: string;
  title: string;
  body: string;
}) {
  return (
    <div className="card group p-6 transition-all duration-200 hover:-translate-y-1 hover:border-line">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-panel2 text-lg transition-all group-hover:shadow-glow">
        <span className={tone}>{icon}</span>
      </div>
      <h3 className="mt-4 font-display text-lg font-semibold text-busy">{title}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-mist">{body}</p>
    </div>
  );
}
