import { useEffect, useState } from "react";
import { EventOut } from "../lib/api";
import { styleFor } from "../lib/categories";
import { niceTime, toHour } from "../lib/format";

const HOUR_MARKS = Array.from({ length: 25 }, (_, i) => i);

/**
 * The signature element: a horizontal 24-hour timeline of a single day.
 * Used on Home (static preview) and Dashboard (live data).
 */
export default function DayRail({
  events,
  height = 68,
  nowMarker = true,
}: {
  events: EventOut[];
  height?: number;
  nowMarker?: boolean;
}) {
  const [hover, setHover] = useState<EventOut | null>(null);
  const sorted = [...events].sort((a, b) => a.start_time.localeCompare(b.start_time));

  return (
    <div className="relative w-full">
      {/* hour labels */}
      <div className="relative mb-1 h-4">
        {HOUR_MARKS.filter((h) => h % 3 === 0).map((h) => (
          <span
            key={`lbl-${h}`}
            className="absolute font-mono text-[9px] text-mist/70"
            style={{ left: `calc(${(h / 24) * 100}% - 12px)` }}
          >
            {h === 24 ? "24:00" : `${String(h).padStart(2, "0")}00`}
          </span>
        ))}
      </div>

      <div
        className="relative w-full overflow-hidden rounded-lg border border-line/70 bg-ink"
        style={{ height }}
      >
        {/* hour ticks */}
        {HOUR_MARKS.map((h) => (
          <div
            key={h}
            className="absolute top-0 h-full border-l border-line/60"
            style={{ left: `${(h / 24) * 100}%` }}
          />
        ))}

        {/* business-hours wash */}
        <div
          className="absolute top-0 h-full bg-free/[0.03]"
          style={{ left: `${(9 / 24) * 100}%`, width: `${((18 - 9) / 24) * 100}%` }}
        />

        {/* booked blocks */}
        {sorted.map((e) => {
          const start = toHour(e.start_time);
          const end = toHour(e.end_time);
          if (end <= start) return null;
          const st = styleFor(e.category);
          const isHover = hover?.id === e.id;
          return (
            <div
              key={e.id}
              onMouseEnter={() => setHover(e)}
              onMouseLeave={() => setHover(null)}
              className={`absolute top-1 z-10 overflow-hidden rounded border px-1.5 py-0.5 text-[10px] leading-tight whitespace-nowrap transition-all duration-150 ${
                isHover ? "z-30 brightness-110 shadow-lg" : ""
              }`}
              style={{
                left: `${(start / 24) * 100}%`,
                width: `${((end - start) / 24) * 100}%`,
                background: isHover ? st.hex : `${st.hex}22`,
                borderColor: isHover ? st.hex : `${st.hex}66`,
                color: st.hex,
                boxShadow: isHover ? `0 0 24px -4px ${st.hex}88` : undefined,
              }}
            >
              {e.title}
            </div>
          );
        })}

        {/* "now" marker */}
        {nowMarker && <NowMarker />}

        {/* tooltip */}
        {hover && (
          <div className="pointer-events-none absolute -top-1 z-40 -translate-y-full rounded-lg border border-line bg-panel2 px-3 py-2 text-xs shadow-float">
            <div className="font-medium text-busy">{hover.title}</div>
            <div className="mt-0.5 font-mono text-[10px]" style={{ color: styleFor(hover.category).hex }}>
              {hover.category} · {niceTime(hover.start_time)} – {niceTime(hover.end_time)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function NowMarker() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  const frac = (now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600) / 24;
  if (frac < 0 || frac > 1) return null;
  return (
    <div className="absolute top-0 bottom-0 z-20 w-[2px] bg-signal" style={{ left: `${frac * 100}%` }}>
      <span className="absolute -left-[3px] top-0 h-[6px] w-[6px] rounded-full bg-signal">
        <span className="absolute inset-0 rounded-full bg-signal animate-ping2" />
      </span>
      <span className="absolute -bottom-1 left-1 font-mono text-[9px] text-signal drop-shadow">
        ●
      </span>
    </div>
  );
}

export function FreeSlotList({ slots }: { slots: { start: string; end: string }[] }) {
  if (!slots.length) {
    return <p className="text-sm text-mist">No free business-hours blocks today.</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {slots.map((s) => (
        <span
          key={s.start}
          className="chip border-free/30 text-free bg-free/5 hover:bg-free/10 transition-colors cursor-default"
        >
          {niceTime(s.start)} – {niceTime(s.end)}
        </span>
      ))}
    </div>
  );
}
