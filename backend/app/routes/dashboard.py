"""Dashboard aggregation route."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import storage
from ..auth import get_current_user
from ..database import get_db
from ..schemas import DashboardOut, EventOut, FreeSlot

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(user=Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today().isoformat()
    today_events = storage.events_today(db, user.id)
    conflicts = storage.detect_conflicts(db, user.id, today)
    upcoming = storage.upcoming_events(db, user.id, days=7)
    schedule_30d = storage.upcoming_events(db, user.id, days=30)
    free = [FreeSlot(**s) for s in storage.free_slots(db, user.id, today)]
    has_defaults = storage.count_default_events(db, user.id) > 0
    return DashboardOut(
        today=today_events,
        conflicts=conflicts,
        upcoming=upcoming,
        schedule_30d=schedule_30d,
        free_slots_today=free,
        has_default_events=has_defaults,
    )
