import { EventOut } from "../lib/api";
import { niceTime } from "../lib/format";
import { styleFor } from "../lib/categories";

export default function ConflictBanner({ conflicts }: { conflicts: EventOut[][] }) {
  if (!conflicts.length) return null;
  return (
    <div className="card mt-5 border-alert/40 p-4 shadow-[0_0_40px_-12px_rgba(224,97,107,0.35)] animate-slideUp">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-alert/20 text-[11px] text-alert">
          !
        </span>
        <span className="font-mono text-xs uppercase tracking-widest text-alert">
          Overlap detected
        </span>
        <span className="ml-auto rounded-full bg-alert/10 px-2 py-0.5 font-mono text-[10px] text-alert">
          {conflicts.length} conflict{conflicts.length > 1 ? "s" : ""}
        </span>
      </div>
      <ul className="mt-2.5 space-y-1.5">
        {conflicts.map(([a, b], i) => {
          const sa = styleFor(a.category);
          const sb = styleFor(b.category);
          return (
            <li key={i} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-busy/90">
              <span className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${sa.bar}`} />
                {a.title}
              </span>
              <span className="font-mono text-[11px] text-mist">
                {niceTime(a.start_time)}–{niceTime(a.end_time)}
              </span>
              <span className="text-mist">overlaps</span>
              <span className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${sb.bar}`} />
                {b.title}
              </span>
              <span className="font-mono text-[11px] text-mist">
                {niceTime(b.start_time)}–{niceTime(b.end_time)}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-mist/80">Ask the assistant to move one — it checks the new slot before writing.</p>
    </div>
  );
}
