import { useState } from "react";
import { Category, EventData } from "../lib/api";
import { styleFor, CATEGORY_ICON } from "../lib/categories";

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const CATEGORIES: Category[] = ["meeting", "workshop", "task", "appointment"];

export default function ScheduleForm({
  initial,
  onSave,
  onCancel,
  saving,
}: {
  initial?: EventData;
  onSave: (d: EventData) => void;
  onCancel: () => void;
  saving?: boolean;
}) {
  const [form, setForm] = useState<EventData>(
    initial ?? {
      title: "",
      event_date: today(),
      start_time: "09:00",
      end_time: "10:00",
      category: "meeting",
      location: "",
      notes: "",
    }
  );
  const set = <K extends keyof EventData>(k: K, v: EventData[K]) => setForm((f) => ({ ...f, [k]: v }));
  const badTime = form.end_time <= form.start_time;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (badTime) return;
        onSave(form);
      }}
      className="card mt-5 grid gap-4 p-6 animate-scaleIn"
    >
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold text-busy">
          {initial ? "Edit event" : "Add an event"}
        </h2>
        <span className="font-mono text-[10px] uppercase tracking-widest text-mist">
          {form.category}
        </span>
      </div>

      {/* category segmented control */}
      <div className="grid grid-cols-4 gap-1.5">
        {CATEGORIES.map((c) => {
          const st = styleFor(c);
          const active = form.category === c;
          return (
            <button
              key={c}
              type="button"
              onClick={() => set("category", c)}
              className={`flex items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-xs capitalize transition-all ${
                active
                  ? "border-transparent text-ink"
                  : "border-line bg-ink/40 text-mist hover:border-line/70 hover:text-busy"
              }`}
              style={active ? { background: st.hex, boxShadow: `0 6px 18px -6px ${st.hex}66` } : undefined}
            >
              <span>{CATEGORY_ICON[c]}</span>
              {c}
            </button>
          );
        })}
      </div>

      <Field label="Title">
        <input
          required
          autoFocus={!initial}
          value={form.title}
          onChange={(e) => set("title", e.target.value)}
          placeholder="e.g. Product review"
          className="input"
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Date">
          <input
            required
            type="date"
            value={form.event_date}
            onChange={(e) => set("event_date", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Start">
          <input
            required
            type="time"
            value={form.start_time}
            onChange={(e) => set("start_time", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="End">
          <input
            required
            type="time"
            value={form.end_time}
            onChange={(e) => set("end_time", e.target.value)}
            className="input"
          />
        </Field>
      </div>

      <Field label="Location">
        <input
          value={form.location ?? ""}
          onChange={(e) => set("location", e.target.value)}
          placeholder="Zoom · Conf room 3 · (optional)"
          className="input"
        />
      </Field>

      <Field label="Notes">
        <textarea
          value={form.notes ?? ""}
          onChange={(e) => set("notes", e.target.value)}
          rows={2}
          placeholder="Context the assistant can search on (optional)"
          className="input"
        />
      </Field>

      {badTime && (
        <p className="text-xs text-alert">End time must be after the start time.</p>
      )}

      <div className="flex gap-3">
        <button type="submit" disabled={saving} className="btn-primary disabled:opacity-60">
          {saving ? "Saving…" : initial ? "Save changes" : "Add event"}
        </button>
        <button type="button" onClick={onCancel} className="btn-ghost">
          Cancel
        </button>
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm text-mist">
      {label}
      <div className="mt-1">{children}</div>
    </label>
  );
}
