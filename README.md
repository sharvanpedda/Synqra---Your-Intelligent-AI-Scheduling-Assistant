# Synqra — Agentic RAG Schedule Assistant

A personal schedule assistant you talk to. It reads your schedule, answers questions in
plain words — by **text or voice** — and speaks the answers back. Under the hood it's an
**agentic RAG** system: a LangGraph agent that retrieves the right events (exact date
lookups **plus** semantic search over embeddings) and uses tools to **add, move, and
delete** events with automatic conflict detection.

**Everything is free.** No paid API. Runs entirely on your machine.

```
Browser (React SPA) ── text / voice ──>  POST /api/agent  ──>  LangGraph agent
   │                                                          │  route → resolve dates
   │  SSE reminders & digest                                  │  → retrieve (RAG) → decide
   ▼                                                          │  → execute tool → answer
FastAPI (Python)                                             ▼
   │── SQLite  (events: source of truth per user)  Tools: get_schedule · update_schedule
   └── ChromaDB (embeddings, local ONNX)          (conflict check + disambiguation built in)
      │
      └── Google Calendar (auto-synced source of truth for event times)
```

| Piece | Choice | Cost |
|---|---|---|
| Backend | FastAPI + LangGraph | $0 |
| Vector DB | ChromaDB (local) | $0 |
| Embeddings | ONNX `all-MiniLM-L6-v2` (local, offline) | $0 |
| LLM | Ollama (local) **or** Groq / Gemini free tier | $0 |
| Speech | Browser Web Speech API (STT + TTS) | $0 |
| Notifications | Server-Sent Events + Browser Notification API | $0 |
| Storage | SQLite + ChromaDB files (per-user) | $0 |
| Auth | Google Sign-In (OAuth 2.0) | $0 |

---

## Quickstart

Requires **Python 3.12+** (tested on 3.14) and **Node 18+**.

### 1. Configure Google OAuth (Required)

1. Go to <https://console.cloud.google.com/apis/credentials>
2. Create an OAuth 2.0 **Web application** client.
3. Add authorized redirect URI:
   `http://127.0.0.1:8005/api/google/callback`
4. Enable **Google Calendar API** in <https://console.cloud.google.com/apis/library>
5. In OAuth consent screen, add scopes:
   - `https://www.googleapis.com/auth/calendar.events`
   - `openid`, `email`, `profile`
6. Note the **Client ID** and **Client Secret**.

### 2. Configure Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows
# ./.venv/bin/pip install -r requirements.txt     # macOS/Linux

# Copy example config and edit
cp .env.example .env
# Edit .env and add:
# GOOGLE_CLIENT_ID=<your-client-id>
# GOOGLE_CLIENT_SECRET=<your-client-secret>
# GOOGLE_CALENDAR_ENABLED=true
```

### 3. Configure Frontend

```bash
cd ../frontend
npm install
# Create .env with:
# VITE_GOOGLE_CLIENT_ID=<your-client-id>
npm run build
```

### 4. Run

```bash
cd ../backend
./.venv/Scripts/python run.py   # Windows
# ./.venv/bin/python run.py     # macOS/Linux
```

Open <http://127.0.0.1:8005> → **Sign in with Google** → Allow calendar access → Start chatting!

### Adding a real LLM (recommended for richer answers)

The agent uses whatever free provider it finds, in this order:

1. **Ollama (local, private)** — `ollama pull llama3.2`, then restart. Auto-detected.
2. **Groq free tier** — put `GROQ_API_KEY` in `backend/.env` (free key at console.groq.com).
3. **Gemini free tier** — put `GEMINI_API_KEY` in `backend/.env`.
4. **Any OpenAI-compatible endpoint** or **Anthropic** — see `backend/.env.example`.

---

## What you can say

| You | It does |
|---|---|
| "What do I have scheduled tomorrow?" | Looks up tomorrow, replies |
| "Am I free Friday afternoon?" | Checks the day, tells you the busy slots |
| "Add a meeting on August 15 at 3 PM" | Adds it — refuses if it conflicts, auto-syncs to Google Calendar |
| "Move my meeting from 2 PM to 4 PM" | Finds the meeting, checks the new slot, moves it, auto-syncs |
| "When is my dentist appointment?" | **Semantic search** over embeddings finds it |
| "What's this week look like?" | Lists the next 7 days |
| "Delete my client call on Friday" | Removes it (asks which one if ambiguous), auto-syncs |

### Voice

Tap the mic in the chat widget (bottom-right). Speak a query; the reply comes back as text
**and is read aloud**. Uses the browser's built-in speech recognition + synthesis — zero cost,
works offline. Best in Chrome/Edge.

### Notifications

- **Reminders**: the backend checks every ~45s and pushes "Your **Team Sync** starts in 10 minutes"
  over SSE the moment an event is about to start.
- **Daily digest**: a morning summary with today's events and any conflicts.
- Click **Allow** on the notification chip to also get native OS notifications.
- "Test notification" button on the Dashboard verifies the whole pipeline.

---

## Project layout

```
backend/
  app/
    config.py        settings (.env)
    database.py      SQLAlchemy engine (SQLite)
    models.py        users / events / sessions
    schemas.py       Pydantic wire models
    auth.py          opaque session tokens + Google token verification
    storage.py       event CRUD + conflict checks + free slots
    embeddings.py    local ONNX embedder (no API)
    vectorstore.py   ChromaDB wrapper (user-scoped)
    rag.py           hybrid retrieval (structured + semantic)
    llm.py           provider abstraction (ollama/groq/gemini/openai/anthropic)
    tools.py         get_schedule / update_schedule definitions + executors (auto-sync)
    fallback.py      deterministic no-LLM parser (safety net)
    agent.py         LangGraph StateGraph — the agentic RAG core
    notifications.py APScheduler reminders + SSE hub
    google_calendar.py  Google Calendar sync (auto-push on changes)
    seed.py          30-day sample data (per-user)
    main.py          FastAPI app (API + static frontend + startup)
  run.py             entrypoint
  requirements.txt
frontend/
  src/               React 18 + Vite + Tailwind SPA (see BUILD_SPEC §7)
  dist/              built bundle (served by FastAPI)
BUILD_SPEC.md        the full technical specification
SETUP_GOOGLE_CALENDAR.md   Google Calendar integration guide
```

---

## API (short version)

`POST /api/auth/google` · `GET /api/auth/me`
`GET /api/events` · `POST /api/events` (409 on conflict) · `PUT /api/events/{id}` · `DELETE /api/events/{id}`
`GET /api/events/search?q=` · `POST /api/agent` · `GET /api/dashboard`
`GET /api/notifications/stream` (SSE) · `GET /api/health`
`GET /api/google/auth-url` · `GET /api/google/callback` · `POST /api/google/sync`

Full contracts in [BUILD_SPEC.md](BUILD_SPEC.md).

---

## Google Calendar Integration

**Required for multi-user.** Google becomes the source of truth for event times while
ChromaDB + the agent stay the search/planning layer. Events are **automatically synced**
to Google Calendar after every agent add/update/delete operation. Manual sync is also
available via `POST /api/google/sync`. See [SETUP_GOOGLE_CALENDAR.md](SETUP_GOOGLE_CALENDAR.md).

---

## Troubleshooting

- **Python 3.14**: all dependencies install cleanly (verified). If `pip install` ever complains,
  upgrade pip first: `python -m pip install --upgrade pip`.
- **"Voice input isn't supported"**: open in Chrome or Edge — Safari/Firefox lack the Web Speech API.
- **No LLM, answers feel scripted**: install Ollama (`ollama pull llama3.2`) or add a free
  Groq/Gemini key. Check `GET /api/health` → `llm_connected`.
- **Port 8005 in use**: set `PORT` in `backend/.env`.
- **Google Sign-In button not showing**: set `VITE_GOOGLE_CLIENT_ID` in `frontend/.env` and rebuild.
- **"Google login is not configured"**: set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `backend/.env`.
- **Re-seed sample data for a user**: `python -m app.seed <user_id> [--force]`

---

## Roadmap notes

- The agent is input-agnostic by design: voice, text, and a future proactive "7 AM digest"
  cron all call the same LangGraph core.
