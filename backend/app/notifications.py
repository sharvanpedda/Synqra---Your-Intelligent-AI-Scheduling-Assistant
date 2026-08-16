"""Reminders + daily digest, delivered over Server-Sent Events.

A background APScheduler job polls the events table every N seconds for events
starting within `REMINDER_LEAD_MIN` minutes (and not already reminded), then
broadcasts a reminder over an SSE hub to that user's connected browser(s). The
browser turns it into a native notification via the Notification API.

Also runs a daily digest at `DIGEST_TIME` summarising the day ahead.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from . import storage
from .config import settings
from .database import SessionLocal
from .models import Event, Session as SessionRow


# --------------------------------------------------------------------------- #
# SSE hub
# --------------------------------------------------------------------------- #
class SSEHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        async with self._lock:
            self._subscribers.setdefault(user_id, []).append(q)
        return q

    async def unsubscribe(self, user_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            queues = self._subscribers.get(user_id, [])
            if q in queues:
                queues.remove(q)
            if not queues:
                self._subscribers.pop(user_id, None)

    async def broadcast(self, user_id: str, event_type: str, data: dict) -> int:
        sent = 0
        payload = json.dumps(data, default=str)
        async with self._lock:
            for q in list(self._subscribers.get(user_id, [])):
                try:
                    q.put_nowait((event_type, payload))
                    sent += 1
                except asyncio.QueueFull:
                    pass
        return sent


hub = SSEHub()


# --------------------------------------------------------------------------- #
# Reminder tracking
# --------------------------------------------------------------------------- #
_reminded: dict[tuple[str, str], str] = {}  # (event_id, start_time) -> when we reminded
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def _fire(user_id: str, event_type: str, data: dict) -> None:
    if _loop is None or _loop.is_closed():
        return
    asyncio.run_coroutine_threadsafe(hub.broadcast(user_id, event_type, data), _loop)


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #
def check_reminders() -> None:
    """Poll for events starting within REMINDER_LEAD_MIN and remind once."""
    db = SessionLocal()
    try:
        now = datetime.now()
        lead = timedelta(minutes=settings.REMINDER_LEAD_MIN)
        window_end = now + lead
        today = date.today().isoformat()
        cutoff = (now + timedelta(days=1)).isoformat()

        rows = db.scalars(
            select(Event).where(
                Event.event_date >= today,
                Event.event_date <= cutoff,
            )
        ).all()

        for e in rows:
            start_dt = _as_datetime(e.event_date, e.start_time)
            if not start_dt:
                continue
            if now <= start_dt <= window_end:
                key = (e.id, e.start_time)
                if key not in _reminded:
                    _reminded[key] = now.isoformat()
                    mins = max(0, int((start_dt - now).total_seconds() // 60))
                    message = f"{e.title} starts in {mins} minute{'s' if mins != 1 else ''} ({e.start_time})."
                    _fire(e.user_id, "reminder", {"event": _event_dict(e), "message": message})
    finally:
        db.close()


def send_daily_digest() -> None:
    db = SessionLocal()
    try:
        today = date.today().isoformat()
        users = db.scalars(select(SessionRow).distinct(SessionRow.user_id)).all()
        seen = {u.user_id for u in users}
        for user_id in seen:
            evs = storage.events_by_day(db, user_id, today)
            conflicts = storage.detect_conflicts(db, user_id, today)
            if not evs and not conflicts:
                continue
            message = f"Good morning! You have {len(evs)} event(s) today."
            if conflicts:
                message += f" ⚠️ {len(conflicts)} overlap(s) detected — check your schedule."
            else:
                message += " No conflicts."
            _fire(user_id, "digest", {"message": message, "events": [_event_dict(e) for e in evs]})
    finally:
        db.close()


def _event_dict(e: Event) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "event_date": e.event_date,
        "start_time": e.start_time,
        "end_time": e.end_time,
        "category": e.category,
        "location": e.location,
        "notes": e.notes,
    }


def _as_datetime(day: str, t: str) -> datetime | None:
    try:
        return datetime.strptime(f"{day} {t}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Scheduler lifecycle
# --------------------------------------------------------------------------- #
scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global scheduler
    if scheduler is not None and scheduler.running:
        return
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_reminders, "interval", seconds=settings.REMINDER_POLL_SECONDS,
                      id="reminders", max_instances=1, coalesce=True)
    hh, mm = settings.DIGEST_TIME.split(":")
    scheduler.add_job(send_daily_digest, "cron", hour=int(hh), minute=int(mm),
                      id="digest", max_instances=1, coalesce=True)
    scheduler.start()
