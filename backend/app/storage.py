"""Event repository — the single place that touches the events table.

All operations are scoped to `user_id` and run a conflict check before any write.
The vector store is kept in sync by the caller (see rag/vectorstore) — storage.py
is pure SQL.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Event
from .schemas import EventData, EventOut

CATEGORY_FREE_SLOT = (9, 18)  # business hours used for free-slot computation


def _to_out(e: Event) -> EventOut:
    return EventOut(
        id=e.id,
        title=e.title,
        event_date=e.event_date,
        start_time=e.start_time,
        end_time=e.end_time,
        category=e.category,  # type: ignore[arg-type]
        location=e.location,
        notes=e.notes,
        source=e.source or "local",
        google_event_id=e.google_event_id,
        is_default=bool(e.is_default),
    )


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return a_start < b_end and a_end > b_start


def list_events(db: Session, user_id: str, date_from: str, date_to: str, category: str | None = None) -> list[EventOut]:
    q = select(Event).where(Event.user_id == user_id, Event.event_date >= date_from, Event.event_date <= date_to)
    if category:
        q = q.where(Event.category == category)
    q = q.order_by(Event.event_date, Event.start_time)
    return [_to_out(e) for e in db.scalars(q).all()]


def get_event(db: Session, user_id: str, event_id: str) -> EventOut | None:
    e = db.scalar(select(Event).where(Event.id == event_id, Event.user_id == user_id))
    return _to_out(e) if e else None


def check_conflict(db: Session, user_id: str, event_date: str, start_time: str, end_time: str,
                   exclude_id: str | None = None) -> list[EventOut]:
    q = select(Event).where(Event.user_id == user_id, Event.event_date == event_date)
    if exclude_id:
        q = q.where(Event.id != exclude_id)
    return [_to_out(e) for e in db.scalars(q).all() if _overlaps(start_time, end_time, e.start_time, e.end_time)]


def add_event(db: Session, user_id: str, data: EventData, is_default: bool = False) -> EventOut:
    data.check_order()
    conflicts = check_conflict(db, user_id, data.event_date, data.start_time, data.end_time)
    if conflicts:
        raise ConflictError(conflicts)
    e = Event(user_id=user_id, is_default=is_default, **data.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return _to_out(e)


def update_event(db: Session, user_id: str, event_id: str, data: EventData) -> EventOut:
    data.check_order()
    e = db.scalar(select(Event).where(Event.id == event_id, Event.user_id == user_id))
    if e is None:
        raise NotFoundError("Event not found")
    conflicts = check_conflict(db, user_id, data.event_date, data.start_time, data.end_time, exclude_id=event_id)
    if conflicts:
        raise ConflictError(conflicts)
    for k, v in data.model_dump().items():
        setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return _to_out(e)


def delete_event(db: Session, user_id: str, event_id: str) -> None:
    e = db.scalar(select(Event).where(Event.id == event_id, Event.user_id == user_id))
    if e is None:
        raise NotFoundError("Event not found")
    db.delete(e)
    db.commit()


def events_by_day(db: Session, user_id: str, day: str) -> list[EventOut]:
    return list_events(db, user_id, day, day)


def events_today(db: Session, user_id: str) -> list[EventOut]:
    return events_by_day(db, user_id, date.today().isoformat())


def count_default_events(db: Session, user_id: str) -> int:
    return int(db.scalar(
        select(func.count(Event.id)).where(Event.user_id == user_id, Event.is_default.is_(True))
    ) or 0)


def upcoming_events(db: Session, user_id: str, days: int = 7) -> list[EventOut]:
    today = date.today().isoformat()
    end = (date.today() + timedelta(days=days)).isoformat()
    return list_events(db, user_id, today, end)


def detect_conflicts(db: Session, user_id: str, day: str) -> list[list[EventOut]]:
    evs = events_by_day(db, user_id, day)
    pairs: list[list[EventOut]] = []
    for i in range(len(evs)):
        for j in range(i + 1, len(evs)):
            a, b = evs[i], evs[j]
            if _overlaps(a.start_time, a.end_time, b.start_time, b.end_time):
                pairs.append([a, b])
    return pairs


def free_slots(db: Session, user_id: str, day: str) -> list[dict]:
    """Free half-hour blocks within business hours (09:00–18:00), in HH:MM format."""
    evs = sorted(events_by_day(db, user_id, day), key=lambda e: e.start_time)
    occupied: list[tuple[str, str]] = [(e.start_time, e.end_time) for e in evs]
    slots: list[dict] = []
    cursor = f"{CATEGORY_FREE_SLOT[0]:02d}:00"
    end_day = f"{CATEGORY_FREE_SLOT[1]:02d}:00"
    while cursor < end_day:
        nxt = _add_minutes(cursor, 30)
        if nxt > end_day:
            break
        if not any(_overlaps(cursor, nxt, s, e) for s, e in occupied):
            slots.append({"start": cursor, "end": nxt})
        cursor = nxt
    return slots


def _add_minutes(t: str, minutes: int) -> str:
    hh, mm = int(t[:2]), int(t[3:])
    total = hh * 60 + mm + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


class ConflictError(Exception):
    def __init__(self, conflicting_events: list[EventOut]):
        super().__init__("conflict")
        self.conflicting_events = conflicting_events


class NotFoundError(Exception):
    pass
