// Server-Sent Events subscription + browser Notification API helpers.
import { EventOut } from "./api";

export interface ReminderPayload {
  event: EventOut;
  message: string;
}

export interface DigestPayload {
  message: string;
  events: EventOut[];
}

export interface NotifyHandlers {
  onReminder: (p: ReminderPayload) => void;
  onDigest: (p: DigestPayload) => void;
  onHello?: () => void;
  onError?: (msg: string) => void;
}

/** Subscribe to the SSE notification stream for a token. Returns unsubscribe. */
export function subscribeToNotifications(token: string, handlers: NotifyHandlers): () => void {
  const es = new EventSource(`/api/notifications/stream?token=${encodeURIComponent(token)}`);

  es.addEventListener("hello", () => handlers.onHello?.());
  es.addEventListener("reminder", (e: MessageEvent) => {
    try {
      handlers.onReminder(JSON.parse(e.data));
    } catch {
      /* ignore malformed */
    }
  });
  es.addEventListener("digest", (e: MessageEvent) => {
    try {
      handlers.onDigest(JSON.parse(e.data));
    } catch {
      /* ignore */
    }
  });
  es.onerror = () => {
    // EventSource auto-reconnects; surface once and let it retry.
    handlers.onError?.("Notification stream disconnected — retrying…");
  };

  return () => es.close();
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  try {
    const res = await Notification.requestPermission();
    return res === "granted";
  } catch {
    return false;
  }
}

export function showBrowserNotification(title: string, body: string, tag?: string): void {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  try {
    new Notification(title, { body, tag, icon: undefined });
  } catch {
    /* some browsers require a service worker for notifications */
  }
}
