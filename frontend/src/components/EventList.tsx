import { EventOut } from "../lib/api";
import { styleFor, CATEGORY_ICON } from "../lib/categories";
import { fullDate, isToday, niceTime } from "../lib/format";

export default function EventList({
  events,
  onEdit,
  onDelete,
  empty,
  compact,
}: {
  events: EventOut[];
  onEdit?: (e: EventOut) => void;
  onDelete?: (id: string) => void;
  empty?: string;
  /** compact: hide per-day headers, used inside the dashboard columns */
  compact?: boolean;
}) {
  const grouped = events.reduce<Record<string, EventOut[]>>((acc, e) => {
    (acc[e.event_date] ??= []).push(e);
    return acc;
  }, {});

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-start gap-1 rounded-lg border border-dashed border-line px-4 py-6 text-sm text-mist">
        <span className="text-lg">☾</span>
        {empty ?? "No events."}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {Object.entries(grouped)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, dayEvents]) => (
          <div key={date}>
            {!compact && (
              <div className="mb-2 flex items-center gap-2.5">
                <span
                  className={`rounded-md px-2 py-0.5 font-mono text-[11px] ${
                    isToday(date)
                      ? "bg-signal/15 text-signal"
                      : "bg-panel text-mist border border-line"
                  }`}
                >
                  {fullDate(date)}
                </span>
                {isToday(date) && (
                  <span className="font-mono text-[10px] text-signal/70">· today</span>
                )}
              </div>
            )}
            <div className="space-y-1.5">
              {dayEvents.map((e) => (
                <EventRow key={e.id} e={e} onEdit={onEdit} onDelete={onDelete} />
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}

function EventRow({
  e,
  onEdit,
  onDelete,
}: {
  e: EventOut;
  onEdit?: (e: EventOut) => void;
  onDelete?: (id: string) => void;
}) {
  const st = styleFor(e.category);
  return (
    <div className="group relative flex items-center gap-3 overflow-hidden rounded-lg border border-line/70 bg-panel/60 py-2.5 pr-3 pl-3 transition-all duration-150 hover:border-line hover:bg-panel2">
      {/* category accent bar */}
      <span className={`h-8 w-[3px] shrink-0 rounded-full ${st.bar}`} />
      {/* time column */}
      <div className="w-[74px] shrink-0 text-right font-mono text-[11px] text-mist">
        <div className="text-[12px] text-busy/90">{niceTime(e.start_time)}</div>
        <div>– {niceTime(e.end_time)}</div>
      </div>
      {/* body */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium text-busy`}>
            <span className={`mr-1.5 ${st.text}`}>{CATEGORY_ICON[e.category as keyof typeof CATEGORY_ICON]}</span>
            {e.title}
          </span>
          {e.source === "google" && (
            <span className="chip border-google/40 text-google bg-google/5">G</span>
          )}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-mist">
          <span className={`chip ${st.chip}`}>{e.category}</span>
          {e.location && (
            <span className="flex items-center gap-0.5">
              <svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a7 7 0 0 0-7 7c0 5.25 7 13 7 13s7-7.75 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z"/></svg>
              {e.location}
            </span>
          )}
        </div>
        {e.notes && <div className="mt-1 truncate text-xs text-mist/70">{e.notes}</div>}
      </div>
      {/* actions (appear on hover) */}
      {(onEdit || onDelete) && (
        <div className="flex shrink-0 gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
          {onEdit && (
            <button
              onClick={() => onEdit(e)}
              className="rounded-md border border-line px-2.5 py-1 text-xs text-mist transition-colors hover:border-free/50 hover:text-free"
            >
              Edit
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(e.id)}
              className="rounded-md border border-line px-2.5 py-1 text-xs text-mist transition-colors hover:border-alert/50 hover:text-alert"
            >
              Delete
            </button>
          )}
        </div>
      )}
    </div>
  );
}
