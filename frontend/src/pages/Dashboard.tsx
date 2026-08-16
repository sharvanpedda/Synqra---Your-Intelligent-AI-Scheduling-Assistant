import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../lib/auth";
import { api, ApiError, Dashboard } from "../lib/api";
import NavBar from "../components/NavBar";
import DayRail, { FreeSlotList } from "../components/DayRail";
import ConflictBanner from "../components/ConflictBanner";
import EventList from "../components/EventList";
import ChatWidget from "../components/ChatWidget";
import NotificationsToasts, { NotificationsTestButton } from "../components/NotificationsToasts";
import { styleFor } from "../lib/categories";
import { longDate } from "../lib/format";

export default function DashboardPage() {
  const { token, user } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(new Date());
  const [removingDefaults, setRemovingDefaults] = useState(false);

  // live clock
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setData(await api.dashboard(token));
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Couldn't load today.");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const nowHHMM = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const todayEvents = data?.today ?? [];
  const nextUp =
    todayEvents
      .filter((e) => e.start_time > nowHHMM)
      .sort((a, b) => a.start_time.localeCompare(b.start_time))[0] ??
    todayEvents.find((e) => e.start_time <= nowHHMM && e.end_time > nowHHMM);
  const nextUpInProgress = nextUp ? nextUp.start_time <= nowHHMM : false;

  const clock = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  const handleRemoveDefaults = useCallback(async () => {
    if (!token) return;
    if (!window.confirm("Remove all default schedules? This only deletes the sample events you didn't create yourself.")) {
      return;
    }
    setRemovingDefaults(true);
    try {
      await api.removeDefaultEvents(token);
      await load();
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't remove default schedules.");
    } finally {
      setRemovingDefaults(false);
    }
  }, [token, load]);

  return (
    <div className="app-bg min-h-screen">
      <NavBar />
      <NotificationsToasts />

      <main className="mx-auto max-w-6xl px-6 pb-16 pt-8">
        {/* header */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-signal">
              {user ? `SIGNED IN · ${user.display_name || user.email}` : "DASHBOARD"}
            </div>
            <h1 className="mt-1 font-display text-3xl font-semibold text-busy">{longDate(todayStr())}</h1>
          </div>
          <div className="flex items-center gap-4">
            {/* live clock */}
            <div className="flex items-center gap-2 rounded-xl border border-line bg-panel px-4 py-2 font-mono">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping2 rounded-full bg-signal" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-signal" />
              </span>
              <span className="text-lg tabular-nums text-busy">{clock}</span>
            </div>
            <NotificationsTestButton />
          </div>
        </div>

        {error && (
          <div className="mt-5 flex items-center justify-between rounded-lg border border-alert/40 bg-alert/10 px-4 py-3 text-sm text-alert">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-xs hover:underline">
              dismiss
            </button>
          </div>
        )}

        {/* next up strip */}
        {nextUp && (
          <div className="card mt-6 flex items-center gap-4 border-free/25 p-4 animate-slideUp">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg"
              style={{ background: `${styleFor(nextUp.category).hex}1f`, color: styleFor(nextUp.category).hex }}
            >
              {nextUp.title.charAt(0).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <div className="font-mono text-[10px] uppercase tracking-widest text-free">
                {nextUpInProgress ? "In progress now" : "Next up"}
              </div>
              <div className="truncate font-medium text-busy">{nextUp.title}</div>
            </div>
            <div className="text-right font-mono text-sm text-mist">
              {nextUp.start_time} – {nextUp.end_time}
            </div>
          </div>
        )}

        {/* day rail */}
        <div className="card mt-6 p-6">
          <div className="mb-5 flex items-center justify-between">
            <span className="font-mono text-xs text-mist">24-HOUR TIMELINE</span>
            <span className="flex items-center gap-1.5 font-mono text-[10px] text-signal">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-signal animate-pulseSoft" /> now
            </span>
          </div>
          {data ? <DayRail events={data.today} height={80} /> : <RailSkeleton />}
        </div>

        {data && <ConflictBanner conflicts={data.conflicts} />}

        {/* top row: today's agenda + next 7 days, side by side */}
        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
          <section className="card p-5">
            <h2 className="mb-3 font-mono text-xs uppercase tracking-widest text-mist">
              Today's agenda
            </h2>
            <EventList events={data?.today ?? []} compact empty="Nothing on the books today." />
          </section>

          <section className="card p-5">
            <h2 className="mb-3 font-mono text-xs uppercase tracking-widest text-mist">
              Next 7 days
            </h2>
            <EventList events={data?.upcoming ?? []} empty="Nothing coming up." />
          </section>
        </div>

        {/* schedule for next 30 days, with free slots at the bottom */}
        <section className="card mt-6 p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-mono text-xs uppercase tracking-widest text-mist">
              Schedule for next 30 days
            </h2>
            {data?.has_default_events && (
              <button
                onClick={handleRemoveDefaults}
                disabled={removingDefaults}
                className="rounded-lg border border-line px-3 py-1.5 text-xs text-mist transition-colors hover:border-alert/50 hover:text-alert disabled:opacity-50"
              >
                {removingDefaults ? "Removing…" : "Remove all default schedules"}
              </button>
            )}
          </div>
          <EventList events={data?.schedule_30d ?? []} empty="Nothing on the books for the next 30 days." />

          <div className="mt-6 border-t border-line/60 pt-5">
            <h3 className="mb-3 font-mono text-xs uppercase tracking-widest text-mist">
              Free slots today
            </h3>
            <FreeSlotList slots={data?.free_slots_today ?? []} />
          </div>
        </section>

        <ChatWidget onScheduleChanged={load} />
      </main>
    </div>
  );
}

function todayStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function RailSkeleton() {
  return (
    <div className="h-[80px] w-full rounded bg-ink">
      <div className="skeleton h-full w-full" />
    </div>
  );
}
