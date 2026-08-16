# Synqra — Build Specification

This spec defines the exact architecture, contracts, and file inventory for building
**Synqra**, an agentic RAG schedule assistant. Read it fully before writing any code. Build targets:

- **Backend**: FastAPI + LangGraph + ChromaDB + SQLite (Python) in `backend/`
- **Frontend**: React 18 + Vite + Tailwind SPA (TypeScript) in `frontend/`, served by FastAPI
- **Free-only**: no paid API required. LLM is pluggable (Ollama local / Groq free / Gemini free /
  OpenAI-compatible / Anthropic). Embeddings are **local ONNX** (no API). Voice = browser Web Speech API.
- **Auth**: Google Sign-In (OAuth 2.0) required for multi-user isolation.

---

## 1. High-level architecture

```
Browser (React SPA, served by FastAPI on :8005)
   │  text / voice → POST /api/agent
   │  SSE ← GET /api/notifications/stream  (reminders + digest)
   ▼
FastAPI (backend/) ─── SQLite (source of truth per user, SQLAlchemy)
   │                ─── ChromaDB (persistent vector store, ONNX MiniLM embeddings, user-scoped)
   │
   ├── LangGraph agent (StateGraph): route → resolve dates → retrieve(RAG) → decide(tool?) → execute → compose
   │     tools: get_schedule, update_schedule   (with conflict check + disambiguation)
   │     LLM: pluggable provider (ollama | groq | gemini | openai_compatible | anthropic)
   │     fallback: deterministic intent parser when no LLM is reachable (bootstrap safety net)
   ├── Reminder scheduler (APScheduler): upcoming-event reminders + daily digest via SSE
   └── Google Calendar sync module (auto-push on add/update/delete, manual pull available)
        └── OAuth 2.0 with nonce-bound state (security: never trust state as user_id)
```

Multi-user via session tokens (opaque, Bearer header). `user_id` is ALWAYS derived server-side
from the verified Google ID token (sub claim), never trusted from request bodies.

---

## 2. Ports & run model

- Single server on port **8005** (configurable via `PORT` env). FastAPI serves `/api/*` and the
  built frontend (`frontend/dist`) as static files. No separate dev servers in production mode.
- Dev: `npm run dev` in `frontend/` proxies `/api` → `http://localhost:8005`.

---

## 3. Data model (SQLite via SQLAlchemy)

`users`: id (text PK = Google `sub`), email (text), display_name (text), auth_source (text: 'google'),
created_at (datetime).

`events`: id (text uuid PK), user_id (text FK, indexed), title, event_date (str 'YYYY-MM-DD'),
start_time (str 'HH:MM'), end_time (str 'HH:MM'), category (str: meeting|workshop|task|appointment),
location (str nullable), notes (str nullable), source (str: 'local'|'google'), google_event_id
(str nullable), created_at, updated_at.

Constraint: `end_time > start_time`. Index: (user_id, event_date).

Every query MUST filter `where user_id = <authed user>`.

## 4. EventData (wire format)

```json
{ "title": "Team Sync", "event_date": "2026-08-14", "start_time": "14:00", "end_time": "15:00",
  "category": "meeting", "location": "Zoom", "notes": "weekly" }
```
category is one of meeting|workshop|task|appointment. Validation: title non-empty, valid date/time
format, end_time > start_time. Times are 24h "HH:MM".

---

## 5. API contract

All JSON. Auth via `Authorization: Bearer <token>` (opaque session token). Error shape:
`{"error": "msg", "code": "conflict"|"not_found"|"auth"|"validation"|..., "conflicting_events": [...]?}`.

### Auth
- `POST /api/auth/google` body `{"id_token": "..."}` → verifies against
  `https://oauth2.googleapis.com/tokeninfo` (aud must match `GOOGLE_CLIENT_ID` when set), upserts
  user (auth_source='google', id = Google `sub`), → `{token, user}`. If `GOOGLE_CLIENT_ID` is unset → 400
  `{"error":"Google login is not configured"}`
- `GET /api/me` → `{user}`
- `POST /api/auth/logout` → 204

### Events (all auth'd)
- `GET /api/events?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&category=meeting`
  → array of EventData+id+source, ordered by event_date, start_time. Default date_from = today,
  date_to = today+30. category optional filter.
- `GET /api/events/today` → today's events (dashboard convenience)
- `GET /api/events/search?q=...` → semantic top-5: `[{...event, similarity: 0..1}]`
- `POST /api/events` body EventData → 201 event | 409 conflict (with `conflicting_events`)
- `PUT /api/events/{id}` body EventData → event | 404 | 409 (conflict check excludes self)
- `DELETE /api/events/{id}` → 204 | 404

### Agent (chat / voice)
- `POST /api/agent` body `{"message": "...", "history": [{"role":"user"|"assistant","content":"..."}]}`
  → `{"reply": "...", "intent": "...", "tool_calls": [{"name","args"}], "events": [EventData+id...]}`
  - `events` = events that were retrieved OR affected by a mutation (so the UI can refresh).
  - `history` optional; used to keep multi-turn context.

### Dashboard
- `GET /api/dashboard` → `{"today": [Event...], "conflicts": [[A,B],...], "upcoming": [Event...],
  "free_slots_today": [{"start":"09:00","end":"10:00"}...]}`

### Notifications (SSE)
- `GET /api/notifications/stream` — Server-Sent Events. Events:
  `event: reminder  data: {"event": Event..., "message": "Team Sync starts in 10 minutes"}`
  `event: digest    data: {"message": "...", "events": [...]}`
- `POST /api/notifications/test` → fires a test reminder (UI demo). 200.

### Health
- `GET /api/health` → `{"status":"ok","llm_provider":"ollama","llm_connected":true|false,
  "rag_indexed": <int count>, "auth":"local"}`

### Google Calendar (optional, default OFF)
- `POST /api/google/sync` body `{"direction":"push"|"pull"}` → `{"pushed":n,"pulled":n,"errors":[]}`.
  Only active when `GOOGLE_CALENDAR_ENABLED=true` + OAuth creds set; else 400.

---

## 6. Backend module inventory (`backend/app/`)

| File | Responsibility |
|---|---|
| `config.py` | Settings via pydantic-settings; reads `.env`. Keys: `PORT`, `DATABASE_PATH`, `CHROMA_PATH`, `SESSION_SECRET`(not needed, opaque tokens), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_CALENDAR_ENABLED`, `LLM_PROVIDER=auto`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `REMINDER_LEAD_MIN=10`, `DIGEST_CRON="07:00"`, `SEED_ON_START=true`, `FRONTEND_DIST=../frontend/dist` |
| `database.py` | SQLAlchemy engine + session factory + init (create tables) |
| `models.py` | ORM: User, Event |
| `schemas.py` | Pydantic: EventData, EventOut, AgentRequest, AgentResponse, LoginLocal, LoginGoogle, DashboardOut, HealthOut |
| `auth.py` | Opaque token store (in-DB table `tokens` or signed value; simplest: DB table `sessions` {token, user_id, created_at, expires_at}), `verify_google_id_token()`, `create_session()`, `get_current_user()` FastAPI dependency |
| `storage.py` | EventRepository: list/range, get, add (with conflict check), update (conflict check excluding self), delete, conflicts_for, free_slots_for. All user-scoped. |
| `embeddings.py` | `Embedder` class wrapping `chromadb.utils.embedding_functions.ONNXMiniLM_L6_V2` (local, free, no API). `embed(texts) -> list[list[float]]` |
| `vectorstore.py` | `VectorStore` wrapping ChromaDB PersistentClient: `index_event(event)`, `delete_event(id)`, `search(query, user_id, top_k)`, `count()`. Collection `events`. Metadata: user_id, event_id, title, date, start, end, category. Documents are the embedding-text: `"{title} — a {category} on {date} from {start} to {end}. {notes}"` |
| `rag.py` | Hybrid retrieval: structured (date/range/category) + semantic (vector). `retrieve(user_id, date_from?, date_to?, query?) -> list[EventOut]` |
| `llm.py` | `LLMClient` provider abstraction with a single `complete(system_prompt, messages) -> str`. Providers via httpx (no langchain wrapper). `auto` resolves: ollama (if `GET {OLLAMA_BASE_URL}/api/tags` ok) → groq (key) → gemini (key) → openai_compatible (base+key) → anthropic (key). `status()` returns provider name + connected. Keep it dependency-light and robust; timeouts ~30s. |
| `tools.py` | Tool defs (JSON schema) for `get_schedule` and `update_schedule` + their `execute()` functions wired to storage + rag. get_schedule args: `{date_from?, date_to?, query?}`. update_schedule args: `{action: add|update|delete, event_data?: EventData, event_id?: str}`. Returns structured result. |
| `fallback.py` | Deterministic intent parser used when LLM is unreachable: recognizes the four canonical query shapes (schedule query, free-check, add, move/update, delete) via regex + date resolution; routes to tools; composes a short reply. Must handle the spec examples: "What do I have scheduled tomorrow?", "Am I free Friday afternoon?", "Add a meeting on August 15 at 3 PM.", "Move my meeting from 2 PM to 4 PM." |
| `agent.py` | **LangGraph StateGraph agent.** Graph state: `{user_id, message, history, resolved_date, intent, tool_calls, tool_result, events, reply, disambiguation}`. Nodes & edges:
   1. `route_intent` → classify (LLM or fallback) into `query_schedule` | `update_schedule` | `chat`
   2. `resolve_dates` → relative dates ("tomorrow","friday","next week") → concrete dates using today
   3. `retrieve` → for query_schedule: hybrid RAG (structured+semantic); for update_schedule: fetch candidate events for disambiguation
   4. `decide` → LLM decides: either answer directly from retrieved context, or emit a `tool_call` JSON (`{"name": "...", "args": {...}}`), or (if ambiguous) emit a clarifying question as final reply
   5. `execute_tool` → run tool, store result
   6. `compose` → LLM writes final reply from tool_result (or fallback composes deterministically)
   7. Conditional edges: `decide`→`compose` if final answer; `decide`→`execute_tool` if tool_call; after tool execution, one extra LLM pass to compose the reply.
   The graph MUST run with or without an LLM (fallback path sets intent/answers deterministically). Export `run_agent(message, history, user_id) -> AgentResponse`. |
| `notifications.py` | APScheduler: every 60s scan events for the active session user(s) starting within `REMINDER_LEAD_MIN` and not yet reminded (track sent via in-memory set keyed by event_id+day+time) → broadcast SSE. Daily digest at `DIGEST_CRON`. `SSEHub` (asyncio queue of subscribers) + `broadcast(type, data)`. |
| `google_calendar.py` | Optional module: OAuth flow + `list_events`/`create_event`/`update_event`/`delete_event` via google-api-python-client; refresh token stored encrypted (Fernet, key from `GOOGLE_TOKEN_KEY` or generated). `sync(user, direction)` pushes local↔calendar or pulls calendar→local, mapping by `google_event_id`. |
| `seed.py` | `seed(user_id, display_name)` — deterministic-ish 30 days of sample events (meeting/workshop/task/appointment) with realistic 9–18h times, using a fixed `random.Random(42)`. Inserts into SQLite + indexes each into Chroma. Called at startup for the local demo user if DB empty (or always idempotent). |
| `main.py` | FastAPI app factory; mounts routers; CORS; static mount for `FRONTEND_DIST`; startup: init DB, seed demo user, warm LLM status, start scheduler. |

`backend/run.py` — entrypoint: `uvicorn.run("app.main:app", host="127.0.0.1", port=settings.PORT)`.

Requirements pinned: fastapi, uvicorn[standard], sqlalchemy, chromadb, langgraph, apscheduler,
httpx, google-auth, google-auth-oauthlib, google-api-python-client, cryptography, python-multipart.

---

## 7. Frontend spec (`frontend/`) — React 18 + Vite + Tailwind + TypeScript

### Design system (from the uploaded zip's design language — keep it faithful)
Dark "control room" palette:
```
ink #0B0E14 (bg) | panel #131824 (cards) | line #232B3A (hairlines) | mist #8A93A6 (secondary text)
signal #F2A65A (amber, active/now) | free #5FD4C0 (teal, open time) | busy #E7E9EE (primary text)
alert #E0616B (conflicts)
```
Fonts: Inter (sans), IBM Plex Mono (mono). Signature element: a **24h day-rail** showing the day
as a horizontal timeline with booked blocks (used on Home + Dashboard).

### Pages / routes (react-router)
- `/` Home — public. Hero headline, short copy, "Sign in with Google" + "Try the live demo"
  (local login) buttons, sample day-rail, three feature bullets.
- `/dashboard` — Today's agenda (day-rail + list), conflict banner, upcoming list, free slots,
  voice+text chat widget (persistent bottom-right), notifications.
- `/schedules` — 30-day grouped event list, add/edit/delete forms, category filter,
  semantic search box ("search your schedule…"), chat widget, notifications.
- Auth: if not logged in, redirect to `/` (or show login overlay). Token stored in localStorage.

### Components (`src/components/`)
- `NavBar.tsx` — brand, links (Dashboard / My Schedules), user email, sign-out.
- `ChatWidget.tsx` — floating bottom-right panel. Message list, text input, voice button,
  thinking indicator. Calls `POST /api/agent`. Supports voice input (mic) + reads replies aloud
  (speech synthesis). Shows tool activity ("agent is checking your schedule…").
- `VoiceButton.tsx` — mic toggle using `webkitSpeechRecognition`.
- `ScheduleForm.tsx` — add/edit event form (title, category, date, start, end, location, notes).
- `EventList.tsx` — grouped-by-date list with edit/delete actions.
- `DayRail.tsx` — the 24h timeline component (props: events). Reusable.
- `ConflictBanner.tsx` — shows detected conflicts.
- `NotificationsToasts.tsx` — subscribes to SSE `GET /api/notifications/stream`, shows in-app
  toasts + browser Notification API (requests permission). Includes "Send test notification" button.
- `LoginScreen.tsx` — Google + demo login, shown when no token.

### `src/lib/`
- `api.ts` — typed API client (fetch wrapper, adds Bearer token, handles 409 etc.)
- `auth.tsx` — AuthContext (token + user + login/logout), persists to localStorage.
- `speech.ts` — helpers: `startListening(onText)`, `speak(text)` (guarded for unsupported browsers).
- `notify.ts` — SSE subscribe + browser notification helpers.

### Behavior contracts
- After any agent reply that may have mutated events, refresh dashboard/schedules (the agent
  response includes `events` — use them, then re-fetch the current view).
- Voice: mic input → transcript shown → sent as text to `/api/agent` → reply rendered + spoken.
  If Web Speech unavailable → show graceful message.
- Notifications: on dashboard mount, request Notification permission; SSE drives toasts.
- Loading/error states everywhere; all API failures surface as readable messages.

### Tooling
Vite + React + TS + Tailwind 3. `vite.config.ts` dev proxy: `/api` → `http://localhost:8005`.
`package.json` scripts: `dev`, `build` (output to `dist`), `preview`.

---

## 8. Deliverable docs (repo root)
- `README.md` — what it is, architecture diagram (ASCII), quickstart (local demo in ~3 commands),
  LLM setup (Ollama recommended free/local; Groq/Gemini free keys; OpenAI-compatible; Anthropic),
  Google Calendar optional setup, voice notes, troubleshooting (py3.14 note), cost = $0.
- `SETUP_GOOGLE_CALENDAR.md` — optional module instructions (OAuth, consent screen, token storage).
- `BUILD_SPEC.md` — this file.

---

## 9. Definition of done
1. Backend imports cleanly; `python run.py` starts on :8005; `/api/health` returns 200.
2. Local demo login works; seed data present (30 days, ~30–45 events).
3. `/api/agent` answers all four spec example queries (with LLM if reachable, else fallback).
4. Conflict check returns 409 on overlap; update excludes self.
5. Semantic search returns relevant events.
6. Frontend builds (vite build) with no TS errors; serves from FastAPI; chat + voice + notifications work.
7. Everything runs with zero paid API keys.
