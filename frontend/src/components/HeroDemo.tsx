import { useEffect, useRef, useState } from "react";

interface Step {
  role: "user" | "assistant";
  text: string;
  /** tool activity chip shown above the assistant bubble */
  tool?: string;
}

const SCRIPT: Step[] = [
  { role: "user", text: "What do I have scheduled tomorrow?" },
  {
    role: "assistant",
    tool: "get_schedule · semantic + date lookup",
    text: "You have a Dentist Appointment at 10:30 AM, then Team Sync at 3:00 PM. You're free after 4.",
  },
  { role: "user", text: "Add a strategy review on Aug 15 at 3 PM." },
  {
    role: "assistant",
    tool: "update_schedule · conflict check",
    text: "Done — added 'Strategy Review' for Aug 15 at 3:00 PM. It didn't conflict with anything.",
  },
  { role: "user", text: "Am I free Friday afternoon?" },
  {
    role: "assistant",
    tool: "get_schedule · free_slots",
    text: "Friday afternoon is open — nothing booked between 1 and 6 PM.",
  },
];

const TYPING_MS = 16;
const PAUSE_MS = 1400;
const MAX_VISIBLE = 4;

/**
 * Sample conversation panel for the hero.
 *
 * It does NOT auto-run: on mount it shows a static first exchange so the panel
 * looks alive without moving, and it only plays the full scripted exchange when
 * the visitor clicks the replay control. The playback is bounded (runs through
 * the script once, then stops) and the rendered bubbles are capped so the card
 * never outgrows the page layout.
 */
export default function HeroDemo() {
  const [lines, setLines] = useState<Step[]>([SCRIPT[0], SCRIPT[1]]);
  const [typingText, setTypingText] = useState("");
  const [typingTool, setTypingTool] = useState<string | undefined>();
  const [speaking, setSpeaking] = useState(false);
  const [playing, setPlaying] = useState(false);
  const timers = useRef<number[]>([]);
  const busyRef = useRef(false);

  // always clear pending timers on unmount
  useEffect(() => () => timers.current.forEach((id) => window.clearTimeout(id)), []);

  const play = () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setPlaying(true);
    setLines([]);
    setTypingText("");
    setTypingTool(undefined);
    setSpeaking(false);

    const t = timers.current;
    const after = (fn: () => void, ms: number) => t.push(window.setTimeout(fn, ms));

    const runStep = (step: number) => {
      if (step >= SCRIPT.length) {
        // finished the script — stop, don't loop
        setPlaying(false);
        busyRef.current = false;
        return;
      }
      const s = SCRIPT[step];
      if (s.role === "user") {
        setLines((ls) => [...ls, s]);
        setTypingText("");
        after(() => runStep(step + 1), 500);
        return;
      }
      // assistant: type out the reply
      setTypingTool(s.tool);
      setTypingText("");
      let i = 0;
      const type = () => {
        i += 1;
        setTypingText(s.text.slice(0, i));
        if (i < s.text.length) {
          after(type, TYPING_MS);
        } else {
          setSpeaking(true);
          after(() => setSpeaking(false), 1600);
          after(() => {
            setLines((ls) => [...ls, { ...s, text: s.text }]);
            setTypingTool(undefined);
            setTypingText("");
            after(() => runStep(step + 1), PAUSE_MS);
          }, 900);
        }
      };
      after(type, 400);
    };

    after(() => runStep(0), 150);
  };

  const visible = lines.slice(-MAX_VISIBLE);

  return (
    <div className="card relative overflow-hidden p-4 shadow-float">
      {/* top chrome */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-signal to-free text-[9px] text-ink">
            ✦
          </span>
          <span className="font-mono text-[10px] text-mist">SCHEDULE AGENT</span>
        </div>
        <span className="flex items-center gap-1.5 font-mono text-[10px] text-free">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping2 rounded-full bg-free" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-free" />
          </span>
          RAG online
        </span>
      </div>

      {/* body */}
      <div className="flex min-h-[180px] flex-col justify-end space-y-3">
        {visible.map((l, i) => (
          <Bubble key={i} line={l} />
        ))}
        {typingText && (
          <div className="flex justify-start">
            <span className="mr-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-signal to-free text-[9px] text-ink">
              ✦
            </span>
            <div className="rounded-2xl rounded-bl-sm border border-line bg-ink/70 px-3.5 py-2.5 text-sm text-busy">
              {typingTool && (
                <div className="mb-1 flex items-center gap-1.5 font-mono text-[10px] text-free">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-free animate-pulseSoft" />
                  {typingTool}
                </div>
              )}
              <span>
                {typingText}
                <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-[2px] bg-free animate-caret" />
              </span>
            </div>
          </div>
        )}
        {speaking && (
          <div className="flex items-center gap-2 px-1 text-free">
            <Wave />
            <span className="font-mono text-[10px]">speaking reply</span>
          </div>
        )}
      </div>

      {/* click to play the sample conversation */}
      <button
        onClick={play}
        disabled={playing}
        className="mt-4 flex w-full items-center gap-2 rounded-xl border border-line bg-ink/60 px-3 py-2.5 transition-colors hover:border-signal/40"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="#8A93A6">
          <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
          <path fillRule="evenodd" clipRule="evenodd" d="M6 11a1 1 0 0 1 1 1 5 5 0 0 0 10 0 1 1 0 1 1 2 0 7 7 0 0 1-6 6.93V21a1 1 0 1 1-2 0v-2.07A7 7 0 0 1 5 12a1 1 0 0 1 1-1Z" />
        </svg>
        <span className="flex-1 text-left text-xs text-mist">
          {playing ? "Playing it back…" : lines.length > 2 ? "↺ Watch again" : "See it in action"}
        </span>
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-signal to-[#e08b4a]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="#14100a">
            <path d="M3 11.5 21 3l-8.5 18-2-7.5L3 11.5Z" />
          </svg>
        </span>
      </button>
    </div>
  );
}

function Bubble({ line }: { line: Step }) {
  if (line.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] rounded-2xl rounded-br-sm bg-gradient-to-br from-signal to-[#e08b4a] px-3.5 py-2.5 text-sm font-medium text-ink">
          {line.text}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <span className="mr-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-signal to-free text-[9px] text-ink">
        ✦
      </span>
      <div className="rounded-2xl rounded-bl-sm border border-line bg-ink/70 px-3.5 py-2.5 text-sm text-busy">
        {line.tool && (
          <div className="mb-1 flex items-center gap-1.5 font-mono text-[10px] text-free">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-free animate-pulseSoft" />
            {line.tool}
          </div>
        )}
        {line.text}
      </div>
    </div>
  );
}

function Wave() {
  return (
    <span className="flex h-4 items-center gap-[2px]">
      {Array.from({ length: 7 }, (_, i) => (
        <span
          key={i}
          className="wave-bar w-[2.5px] rounded-full bg-free"
          style={{ height: `${8 + ((i * 5) % 7)}px`, animationDelay: `${(i % 7) * 0.12}s` }}
        />
      ))}
    </span>
  );
}
