import { useEffect, useRef, useState } from "react";
import { speechSupported, startListening } from "../lib/speech";

/**
 * Mic button. Tap to start listening; the browser's own speech recognizer
 * auto-stops once it detects the end of speech (or tap again to stop early),
 * and hands the transcript back via onText — what the caller does with it
 * (drop it in the composer for review, or send it straight away) is up to
 * them. Runs entirely client-side — no backend call, no API key.
 */
export default function VoiceButton({
  onText,
  onError,
  disabled,
}: {
  onText: (text: string) => void;
  /** Called with a human-readable message whenever a voice turn fails
   * (mic permission denied, no speech detected, or the browser's
   * recognizer erroring out). Wire this up to show the actual error
   * instead of letting the button just quietly go back to idle. */
  onError?: (msg: string) => void;
  disabled?: boolean;
}) {
  const [listening, setListening] = useState(false);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => () => stopRef.current?.(), []);

  const supported = speechSupported();

  const toggle = () => {
    if (listening) {
      // Manual stop tap — the onEnd callback below (fired by the
      // recognizer's own onend, whether triggered by this stop() call or
      // the recognizer detecting end-of-speech on its own) is the single
      // source of truth for clearing `listening`.
      stopRef.current?.();
      return;
    }
    setListening(true);
    stopRef.current = startListening(
      (text) => onText(text),
      () => setListening(false),
      (msg) => onError?.(msg)
    );
  };

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled || !supported}
      title={
        supported
          ? listening
            ? "Listening — stops automatically, or tap to stop now"
            : "Speak your query"
          : "Voice input isn't supported in this browser — try Chrome or Edge"
      }
      aria-label="Voice input"
      className={`relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-all ${
        listening
          ? "border-alert/70 bg-alert/15 text-alert"
          : "border-line bg-panel text-mist hover:border-signal/60 hover:text-signal"
      } disabled:cursor-not-allowed disabled:opacity-40`}
    >
      {listening && (
        <span className="absolute inset-0 rounded-full border border-alert/50 animate-pulseRing" />
      )}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6 11a1 1 0 0 1 1 1 5 5 0 0 0 10 0 1 1 0 1 1 2 0 7 7 0 0 1-6 6.93V21a1 1 0 1 1-2 0v-2.07A7 7 0 0 1 5 12a1 1 0 0 1 1-1Z"
        />
      </svg>
    </button>
  );
}
