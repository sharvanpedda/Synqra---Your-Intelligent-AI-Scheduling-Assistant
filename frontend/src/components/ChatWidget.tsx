import { useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/auth";
import { api, AgentResponse, ChatTurn, EventOut } from "../lib/api";
import { speak, stopSpeaking, ttsSupported, speechSupported } from "../lib/speech";
import VoiceButton from "./VoiceButton";
import Waveform from "./Waveform";

interface Msg {
  role: "user" | "assistant";
  content: string;
  toolCalls?: string[];
  changed?: EventOut[];
}

const SUGGESTIONS = [
  "What do I have tomorrow?",
  "Am I free Friday afternoon?",
  "Add a meeting on August 15 at 3 PM",
  "When is my dentist appointment?",
  "Show me this week's schedule",
  "Move my 2 PM to 4 PM",
];

const TOOL_LABEL: Record<string, string> = {
  get_schedule: "checking your schedule",
  update_schedule: "updating your schedule",
};

/**
 * Whether a voice transcript is sent to the agent automatically, or just
 * dropped into the text box for the user to review/edit and send manually.
 * Now enabled — voice input automatically sent when speech ends (no duplicates).
 */
const VOICE_AUTO_SEND = true;

export default function ChatWidget({
  onScheduleChanged,
}: {
  onScheduleChanged?: () => void;
}) {
  const { token } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [speakOn, setSpeakOn] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const historyRef = useRef<ChatTurn[]>([]);
  const [quick, setQuick] = useState(() => SUGGESTIONS[Math.floor(Math.random() * SUGGESTIONS.length)]);

  const rotateQuick = () => {
    setQuick(SUGGESTIONS[Math.floor(Math.random() * SUGGESTIONS.length)]);
  };

  const [voiceEnabled, setVoiceEnabled] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .voiceStatus(token)
      .then((s) => setVoiceEnabled(s.enabled))
      .catch(() => setVoiceEnabled(false));
  }, [token]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  // Focus the composer when the panel opens; Esc closes it.
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        stopSpeaking();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const pushMsg = (m: Msg) => setMessages((ms) => [...ms, m]);

  async function send(text?: string) {
    const content = (text ?? input).trim();
    if (!content || !token || busy) return;
    setInput("");
    setError(null);
    pushMsg({ role: "user", content });
    setBusy(true);
    try {
      const res: AgentResponse = await api.askAgent(token, content, historyRef.current);
      historyRef.current = [...historyRef.current.slice(-20), { role: "user", content }];
      const toolCalls = res.tool_calls.map((t) => t.name);
      pushMsg({
        role: "assistant",
        content: res.reply,
        toolCalls: toolCalls.length ? toolCalls : undefined,
        changed: res.events?.length ? res.events : undefined,
      });
      historyRef.current = [...historyRef.current, { role: "assistant", content: res.reply }];
      if (speakOn && voiceEnabled && res.reply && ttsSupported() && token) {
        setSpeaking(true);
        speak(
          token,
          res.reply,
          () => setSpeaking(true),
          () => setSpeaking(false),
          (err) => {
            setError("Voice reply error: " + err);
            setSpeaking(false);
          }
        );
      }
      if (toolCalls.some((t) => t === "update_schedule")) onScheduleChanged?.();
    } catch (e: any) {
      setError(e?.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const toolLabel = (name: string) => TOOL_LABEL[name] || `running ${name}`;
  const canSpeak = voiceEnabled && ttsSupported();
  // Speech-to-text is now the browser's own built-in recognizer — it needs
  // no backend/Sarvam configuration at all, just browser support. Gating it
  // on `voiceEnabled` (which reflects whether Sarvam is configured, for TTS)
  // would hide the mic button on deployments that haven't set up Sarvam,
  // even though voice input would work fine without it.
  const canListen = speechSupported();

  return (
    <>
      {/* launcher orb */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close assistant" : "Open assistant"}
        className={`group fixed bottom-6 right-6 z-40 flex items-center justify-center rounded-full transition-all duration-200 hover:scale-110 ${
          open ? "rotate-45" : ""
        }`}
        style={{
          width: 60,
          height: 60,
          background: "linear-gradient(135deg, #F2A65A 0%, #e08b4a 55%, #5FD4C0 130%)",
          boxShadow: "0 12px 40px -8px rgba(242,166,90,0.55)",
        }}
      >
        {open ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14100a" strokeWidth="2.6" strokeLinecap="round">
            <path d="M5 5l14 14M19 5L5 19" />
          </svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="#14100a">
            <path d="M4 4h16v11H7l-3 3V4Zm2 3v1h12V7H6Zm0 3v1h12v-1H6Z" />
          </svg>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Schedule assistant chat"
          className="fixed bottom-24 right-6 z-40 flex h-[min(560px,72vh)] w-[min(94vw,400px)] flex-col overflow-hidden rounded-2xl border border-line bg-panel/95 shadow-float backdrop-blur-xl animate-slideUp"
        >
          {/* header */}
          <div className="flex items-center justify-between border-b border-line bg-ink/40 px-4 py-3">
            <div className="flex items-center gap-2.5">
              <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-signal to-free text-xs text-ink">
                ✦
                <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-panel bg-free" />
              </span>
              <div>
                <div className="font-display text-sm font-semibold leading-tight text-busy">
                  Synqra
                </div>
                <div className="font-mono text-[10px] text-mist">
                  agentic RAG · {canListen ? "voice-ready" : "text mode"}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              {canSpeak && (
                <button
                  onClick={() => {
                    setSpeakOn((s) => {
                      if (s) stopSpeaking();
                      return !s;
                    });
                  }}
                  title={speakOn ? "Mute replies" : "Read replies aloud"}
                  className={`rounded-lg px-2 py-1 text-xs transition-colors ${
                    speakOn ? "text-free bg-free/10" : "text-mist hover:text-busy"
                  }`}
                >
                  {speakOn ? "🔊 on" : "🔇 off"}
                </button>
              )}
              <button
                onClick={() => {
                  stopSpeaking();
                  setOpen(false);
                }}
                className="rounded-lg px-2 py-1 text-mist hover:bg-panel2 hover:text-busy"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
          </div>

          {/* messages */}
          <div ref={listRef} className="flex-1 space-y-3.5 overflow-y-auto px-4 py-4">
            {messages.length === 0 && (
              <div className="space-y-3 pt-1">
                <div className="rounded-xl border border-line bg-ink/50 p-3.5 text-[13px] text-mist">
                  <p>
                    I read your real schedule before I answer. Ask by{" "}
                    <span className="text-busy">typing</span> or{" "}
                    <span className="text-busy">voice</span> — I reply the same way.
                  </p>
                </div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-mist/80">
                  Try saying
                </div>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.slice(0, 4).map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-full border border-line bg-ink/50 px-3 py-1.5 text-xs text-mist transition-all hover:border-signal/50 hover:text-busy hover:shadow-glow"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                {m.role === "assistant" && (
                  <span className="mr-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-signal to-free text-[9px] text-ink">
                    ✦
                  </span>
                )}
                <div
                  className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "rounded-br-sm bg-gradient-to-br from-signal to-[#e08b4a] font-medium text-ink"
                      : "rounded-bl-sm border border-line bg-ink/60 text-busy"
                  }`}
                >
                  {/* tool activity */}
                  {m.toolCalls?.map((t) => (
                    <div key={t} className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] text-free">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-free animate-pulseSoft" />
                      ◉ {toolLabel(t)}
                    </div>
                  ))}
                  {m.content}
                  {m.changed && m.changed.length > 0 && (
                    <div className="mt-1.5 flex items-center gap-1 border-t border-line/60 pt-1.5 text-[10px] text-mist">
                      <span className="text-free">✓</span> {m.changed.length} event(s) updated
                    </div>
                  )}
                  {/* speaking waveform */}
                  {m.role === "assistant" && speaking && i === messages.length - 1 && (
                    <div className="mt-1.5 flex items-center gap-2">
                      <Waveform bars={7} color="#5FD4C0" />
                      <span className="font-mono text-[10px] text-free">speaking</span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* thinking */}
            {busy && (
              <div className="flex justify-start">
                <span className="mr-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-signal to-free text-[9px] text-ink animate-pulseSoft">
                  ✦
                </span>
                <div className="rounded-2xl rounded-bl-sm border border-line bg-ink/60 px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="type-dot inline-block h-1.5 w-1.5 rounded-full bg-free" />
                    <span className="type-dot inline-block h-1.5 w-1.5 rounded-full bg-free" />
                    <span className="type-dot inline-block h-1.5 w-1.5 rounded-full bg-free" />
                    <span className="ml-1 font-mono text-[10px] text-mist">reasoning…</span>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <p className="rounded-lg border border-alert/30 bg-alert/10 px-3 py-2 text-xs text-alert">
                {error}
              </p>
            )}
          </div>

          {/* quick suggestion + input */}
          <div className="border-t border-line bg-ink/30 p-3">
            <div className="mb-2 flex items-center gap-2">
              <span className="font-mono text-[9px] uppercase tracking-widest text-mist/80">or</span>
              <button
                onClick={() => {
                  send(quick);
                  rotateQuick();
                }}
                disabled={busy}
                className="truncate rounded-full border border-dashed border-line px-3 py-1 text-xs text-mist transition-colors hover:border-free/50 hover:text-free"
                title="Tap for a random example"
              >
                {quick}
              </button>
            </div>
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder="Ask about your schedule…"
                className="input flex-1"
                disabled={busy}
                aria-label="Message"
              />
              {canListen && (
                <VoiceButton
                  onError={(msg) => setError(msg)}
                  onText={(t) => {
                    setError(null);
                    if (VOICE_AUTO_SEND) {
                      send(t);
                      return;
                    }
                    // Drop the transcript into the box for the user to
                    // review/edit — they click Send when ready, same as
                    // typed text. Focus + put the cursor at the end so
                    // they can start editing immediately if needed.
                    setInput(t);
                    requestAnimationFrame(() => {
                      const el = inputRef.current;
                      if (el) {
                        el.focus();
                        el.setSelectionRange(el.value.length, el.value.length);
                      }
                    });
                  }}
                  disabled={busy}
                />
              )}
              <button
                onClick={() => send()}
                disabled={busy || !input.trim()}
                className="btn-primary flex h-9 w-9 items-center justify-center rounded-full p-0 disabled:opacity-40"
                aria-label="Send"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3 11.5 21 3l-8.5 18-2-7.5L3 11.5Z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
