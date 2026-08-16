"""FastAPI application — API + static frontend + background jobs."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .llm import get_llm
from .notifications import set_loop, start_scheduler
from .routes import agent, auth, dashboard, events, google, notifications, voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    init_db()
    set_loop(asyncio.get_running_loop())
    start_scheduler()
    llm = get_llm()
    print(f"[synqra] LLM: {llm.provider or 'none'} "
          f"(connected={llm.connected}) — fallback parser active" if not llm.connected
          else f"[synqra] LLM: {llm.provider} ({llm.model})")
    yield
    # --- shutdown ---
    from .notifications import scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Synqra — Agentic RAG Schedule Assistant", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8005"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(agent.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(google.router)
app.include_router(voice.router)


@app.get("/api/health")
def health():
    llm = get_llm()
    from .vectorstore import get_vectorstore
    try:
        rag_indexed = get_vectorstore().count()
    except Exception:
        rag_indexed = 0
    return {
        "status": "ok",
        "llm_provider": llm.provider,
        "llm_connected": llm.connected,
        "rag_indexed": rag_indexed,
        "auth": "google",
        "voice_enabled": settings.voice_enabled,
    }


# --- static frontend (built React SPA) ---
_dist = Path(settings.FRONTEND_DIST)
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    from fastapi.responses import JSONResponse

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        if full_path.startswith("assets/"):
            return FileResponse(_dist / "index.html")  # app shell fallback
        candidate = _dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
else:
    @app.get("/")
    def index_not_built():
        return {"detail": "Frontend not built yet. Run `npm install && npm run build` in frontend/, then restart."}
