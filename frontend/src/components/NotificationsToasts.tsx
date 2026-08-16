import { useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/auth";
import { api, EventOut } from "../lib/api";
import { requestNotificationPermission, showBrowserNotification, subscribeToNotifications } from "../lib/notify";

interface Toast {
  id: number;
  title: string;
  body: string;
  tone: "reminder" | "digest";
}

/**
 * Subscribes to the SSE stream once authenticated, renders in-app toasts, and
 * raises native browser notifications.
 */
export default function NotificationsToasts() {
  const { token } = useAuth();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [perm, setPerm] = useState<NotificationPermission | "unsupported">(() => {
    if (!("Notification" in window)) return "unsupported";
    if (Notification.permission !== "default") return Notification.permission;
    try {
      if (sessionStorage.getItem("schedule_notify_dismissed")) return "denied";
    } catch {
      /* ignore */
    }
    return "default";
  });
  const idRef = useRef(0);

  useEffect(() => {
    if (!token) return;
    const push = (tone: Toast["tone"], title: string, body: string, ev?: EventOut) => {
      const id = ++idRef.current;
      setToasts((ts) => [{ id, title, body, tone }, ...ts].slice(0, 4));
      showBrowserNotification(title, body, ev?.id);
      setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), 8000);
    };
    const unsub = subscribeToNotifications(token, {
      onReminder: (p) => push("reminder", "Upcoming", p.message, p.event),
      onDigest: (p) => push("digest", "Daily digest", p.message),
    });
    return unsub;
  }, [token]);

  const enable = async () => {
    const ok = await requestNotificationPermission();
    setPerm(ok ? "granted" : "denied");
  };

  const dismissChip = () => {
    try {
      sessionStorage.setItem("schedule_notify_dismissed", "1");
    } catch {
      /* ignore */
    }
    setPerm("denied"); // hide the chip for this session
  };

  const dismiss = (id: number) => setToasts((ts) => ts.filter((t) => t.id !== id));

  return (
    <>
      {/* permission chip — only while the browser has not decided yet */}
      {token && perm === "default" && (
        <div className="fixed right-6 top-4 z-50 flex items-center gap-3 rounded-xl border border-line bg-panel/90 px-4 py-2.5 text-sm text-mist shadow-float backdrop-blur-md animate-slideUp">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping2 rounded-full bg-signal" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-signal" />
          </span>
          <span>Enable schedule alerts?</span>
          <button onClick={enable} className="font-medium text-signal hover:underline">
            Allow
          </button>
          <button
            onClick={dismissChip}
            aria-label="Dismiss"
            className="rounded-md px-1.5 text-mist/70 transition-colors hover:bg-panel2 hover:text-busy"
          >
            ✕
          </button>
        </div>
      )}

      {/* in-app toasts */}
      <div className="pointer-events-none fixed right-4 bottom-24 z-50 flex w-[min(92vw,360px)] flex-col gap-2">
        {toasts.map((t) => {
          const isReminder = t.tone === "reminder";
          return (
            <button
              key={t.id}
              onClick={() => dismiss(t.id)}
              className={`pointer-events-auto card animate-slideUp p-4 text-left shadow-float backdrop-blur-md ${
                isReminder ? "border-signal/40" : "border-free/30"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] ${
                    isReminder ? "bg-signal/15 text-signal" : "bg-free/15 text-free"
                  }`}
                >
                  {isReminder ? "⏰" : "☀"}
                </span>
                <span
                  className={`font-mono text-[10px] uppercase tracking-widest ${
                    isReminder ? "text-signal" : "text-free"
                  }`}
                >
                  {t.title}
                </span>
                <span className="ml-auto text-mist/50">✕</span>
              </div>
              <div className="mt-1.5 text-sm text-busy">{t.body}</div>
            </button>
          );
        })}
      </div>
    </>
  );
}

export function NotificationsTestButton() {
  const { token } = useAuth();
  const [sent, setSent] = useState(false);
  return (
    <button
      onClick={async () => {
        if (!token) return;
        try {
          await api.testNotification(token);
          setSent(true);
          setTimeout(() => setSent(false), 2200);
        } catch {
          /* ignore */
        }
      }}
      className="btn-ghost text-xs"
    >
      {sent ? "✓ Sent" : "Test notification"}
    </button>
  );
}
