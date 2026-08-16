// Typed API client. Token is passed explicitly so the auth context owns storage.
export type Category = "meeting" | "workshop" | "task" | "appointment";

export interface EventData {
  title: string;
  event_date: string; // YYYY-MM-DD
  start_time: string; // HH:MM
  end_time: string;   // HH:MM
  category: Category;
  location?: string;
  notes?: string;
}

export interface EventOut extends EventData {
  id: string;
  source: string;
  is_default?: boolean;
  similarity?: number;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  auth_source: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface ToolCallOut {
  name: string;
  args: Record<string, unknown>;
}

export interface AgentResponse {
  reply: string;
  intent: string;
  tool_calls: ToolCallOut[];
  events: EventOut[];
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface Dashboard {
  today: EventOut[];
  conflicts: EventOut[][];
  upcoming: EventOut[];
  schedule_30d: EventOut[];
  free_slots_today: { start: string; end: string }[];
  has_default_events: boolean;
}

export class ApiError extends Error {
  status: number;
  conflicting_events?: EventOut[];
  constructor(status: number, message: string, conflicting?: EventOut[]) {
    super(message);
    this.status = status;
    this.conflicting_events = conflicting;
  }
}

const BASE = "";

/** Fired once when the server says our session token is no longer valid. */
export const AUTH_EXPIRED_EVENT = "schedule-auth-expired";

export function dispatchAuthExpired(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
}

async function request<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers as object) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && token) {
    dispatchAuthExpired();
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      /* ignore */
    }
    const msg =
      (detail as { detail?: string | { error?: string } })?.detail &&
      typeof (detail as { detail: unknown }).detail === "string"
        ? ((detail as { detail: string }).detail)
        : (detail as { error?: string })?.error ||
          (detail as { detail?: { error?: string } })?.detail?.error ||
          `Request failed (${res.status})`;
    throw new ApiError(res.status, msg, (detail as { conflicting_events?: EventOut[] })?.conflicting_events);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  loginGoogle: (id_token: string) =>
    request<AuthResponse>("/api/auth/google", null, { method: "POST", body: JSON.stringify({ id_token }) }),

  logout: (token: string) => request<void>("/api/auth/logout", token, { method: "POST" }),

  me: (token: string) => request<User>("/api/auth/me", token),

  events: (token: string, params: { date_from?: string; date_to?: string; category?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.date_from) q.set("date_from", params.date_from);
    if (params.date_to) q.set("date_to", params.date_to);
    if (params.category) q.set("category", params.category);
    const s = q.toString();
    return request<EventOut[]>(`/api/events${s ? `?${s}` : ""}`, token);
  },

  today: (token: string) => request<EventOut[]>("/api/events/today", token),

  search: (token: string, q: string) => request<EventOut[]>(`/api/events/search?q=${encodeURIComponent(q)}`, token),

  addEvent: (token: string, data: EventData) =>
    request<EventOut>("/api/events", token, { method: "POST", body: JSON.stringify(data) }),

  updateEvent: (token: string, id: string, data: EventData) =>
    request<EventOut>(`/api/events/${id}`, token, { method: "PUT", body: JSON.stringify(data) }),

  deleteEvent: (token: string, id: string) => request<void>(`/api/events/${id}`, token, { method: "DELETE" }),

  removeDefaultEvents: (token: string) =>
    request<{ removed: number }>("/api/events/defaults", token, { method: "DELETE" }),

  askAgent: (token: string, message: string, history: ChatTurn[]) =>
    request<AgentResponse>("/api/agent", token, {
      method: "POST",
      body: JSON.stringify({ message, history }),
    }),

  dashboard: (token: string) => request<Dashboard>("/api/dashboard", token),

  testNotification: (token: string) => request<{ ok: boolean }>("/api/notifications/test", token, { method: "POST" }),

  health: () =>
    request<{ status: string; llm_provider: string; llm_connected: boolean; rag_indexed: number; voice_enabled?: boolean }>(
      "/api/health",
      null
    ),

  voiceStatus: (token: string) => request<{ enabled: boolean }>("/api/voice/status", token),

  /** Upload a recorded audio blob, get back the transcribed text. */
  speechToText: async (token: string, audio: Blob): Promise<string> => {
    const form = new FormData();
    const ext = audio.type.includes("wav") ? "wav" : audio.type.includes("mp4") ? "m4a" : "webm";
    form.append("file", audio, `speech.${ext}`);
    const res = await fetch(`${BASE}/api/voice/stt`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (res.status === 401) dispatchAuthExpired();
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      throw new ApiError(res.status, (detail as { detail?: string })?.detail || "Voice transcription failed");
    }
    const body = (await res.json()) as { text: string };
    return body.text;
  },

  /** Send text, get back playable audio (object URL — caller should revokeObjectURL when done). */
  /** URL for the streaming TTS endpoint — point an <audio> element's src at
   * this directly (rather than fetching it) so playback starts on the first
   * audio chunk instead of waiting for the whole reply to finish
   * synthesizing. <audio> elements can't set an Authorization header, so the
   * session token travels as a query param here — see
   * get_current_user_allow_query_token in the backend, which only accepts
   * that for this one route. */
  textToSpeechStreamUrl: (token: string, text: string): string => {
    const params = new URLSearchParams({ text, token });
    return `${BASE}/api/voice/tts/stream?${params.toString()}`;
  },
};
