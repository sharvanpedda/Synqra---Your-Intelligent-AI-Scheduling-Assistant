import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../lib/auth";
import { api, ApiError, Category, EventData, EventOut } from "../lib/api";
import NavBar from "../components/NavBar";
import EventList from "../components/EventList";
import ScheduleForm from "../components/ScheduleForm";
import ChatWidget from "../components/ChatWidget";
import NotificationsToasts from "../components/NotificationsToasts";
import { styleFor } from "../lib/categories";
import { localDateStr } from "../lib/format";

const CATEGORIES: (Category | "all")[] = ["all", "meeting", "workshop", "task", "appointment"];

export default function SchedulesPage() {
  const { token } = useAuth();
  const [events, setEvents] = useState<EventOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EventOut | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState<Category | "all">("all");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchActive, setSearchActive] = useState(false);

  const range = useMemo(() => {
    const to = new Date();
    to.setDate(to.getDate() + 30);
    return { date_from: localDateStr(), date_to: localDateStr(to) };
  }, []);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setEvents(await api.events(token, range));
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Couldn't load your schedule.");
    }
  }, [token, range]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(
    () => (filter === "all" ? events : events.filter((e) => e.category === filter)),
    [events, filter]
  );

  const handleSave = async (data: EventData) => {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      if (editing) await api.updateEvent(token, editing.id, data);
      else await api.addEvent(token, data);
      setShowForm(false);
      setEditing(null);
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const clash = e.conflicting_events?.map((c) => c.title).join(", ") || "another event";
        setError(`That time overlaps ${clash} — pick a different slot.`);
      } else {
        setError((e as Error).message);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!token || !confirm("Delete this event?")) return;
    try {
      await api.deleteEvent(token, id);
      await load();
    } catch (e: any) {
      setError(e?.message || "Delete failed.");
    }
  };

  const runSearch = async () => {
    if (!token) return;
    if (!query.trim()) {
      setSearchActive(false);
      await load();
      return;
    }
    setSearching(true);
    setSearchActive(true);
    try {
      setEvents(await api.search(token, query.trim()));
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Search failed.");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="app-bg min-h-screen">
      <NavBar />
      <NotificationsToasts />

      <main className="mx-auto max-w-6xl px-6 pb-16 pt-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-signal">MY SCHEDULES</div>
            <h1 className="mt-1 font-display text-3xl font-semibold text-busy">Next 30 days</h1>
            <p className="mt-0.5 text-sm text-mist">
              {searchActive ? "semantic results" : `${filtered.length} events · ${filter === "all" ? "all types" : filter}`}
            </p>
          </div>
          <button onClick={() => { setShowForm(true); setEditing(null); }} className="btn-primary">
            + Add event
          </button>
        </div>

        {/* search + filter */}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <svg
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mist"
              width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
              placeholder="Semantic search… e.g. “dentist” or “workshop about slides”"
              className="input pl-9"
            />
            {searchActive && (
              <button
                onClick={() => { setQuery(""); setSearchActive(false); load(); }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-[10px] text-mist hover:text-busy"
              >
                ✕
              </button>
            )}
          </div>
          <button onClick={runSearch} disabled={searching} className="btn-ghost text-sm">
            {searching ? "Searching…" : "Search"}
          </button>
        </div>

        {/* filter pills */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => {
            const active = filter === c;
            const st = c === "all" ? null : styleFor(c);
            return (
              <button
                key={c}
                onClick={() => setFilter(c)}
                className={`chip capitalize transition-all ${
                  active
                    ? st
                      ? `${st.chip} border-transparent`
                      : "border-signal text-signal bg-signal/10"
                    : "hover:border-line hover:text-busy"
                }`}
              >
                {c === "all" ? `all (${events.length})` : c}
              </button>
            );
          })}
        </div>

        {error && (
          <div className="mt-4 flex items-center justify-between rounded-lg border border-alert/40 bg-alert/10 px-4 py-3 text-sm text-alert animate-slideUp">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="ml-3 text-xs hover:underline">
              dismiss
            </button>
          </div>
        )}

        {/* form */}
        {showForm && (
          <ScheduleForm
            initial={editing ?? undefined}
            onSave={handleSave}
            onCancel={() => { setShowForm(false); setEditing(null); }}
            saving={saving}
          />
        )}

        <div className="mt-6">
          <EventList
            events={filtered}
            onEdit={(e) => { setEditing(e); setShowForm(true); window.scrollTo({ top: 0, behavior: "smooth" }); }}
            onDelete={handleDelete}
            empty={searchActive ? "No events match that search." : "No events match."}
          />
        </div>

        <ChatWidget onScheduleChanged={load} />
      </main>
    </div>
  );
}
