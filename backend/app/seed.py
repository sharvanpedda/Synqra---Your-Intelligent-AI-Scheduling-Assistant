"""Seed a 30-day sample schedule for a given user (deterministic).

Generates ~35-50 events across meeting / workshop / task /
appointment categories with realistic business-hours times, stores them in SQLite
and indexes each into ChromaDB so semantic search works immediately.

Run explicitly with a user_id:
    python -m app.seed <user_id>   (seeds the given user)
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import storage
from .database import SessionLocal, init_db
from .models import Event
from .schemas import EventData
from .vectorstore import get_vectorstore

TITLES: dict[str, list[str]] = {
    "meeting": ["Team Sync", "Client Call", "1:1 with Manager", "Sprint Planning",
                "Budget Review", "Stakeholder Sync", "Product Demo", "Interview Loop"],
    "workshop": ["React Workshop", "Agentic AI Bootcamp", "Design Thinking Session",
                 "SQL Deep Dive", "Public Speaking Practice", "LLM Fine-tuning Lab"],
    "task": ["Finish Q3 Report", "Review PRs", "Update Portfolio", "Prep Slides",
             "Submit Expense Claims", "Email Triage", "Deploy Fix", "Write Docs"],
    "appointment": ["Dentist Appointment", "Doctor Checkup", "Haircut", "Bank Visit",
                    "Physio Session", "Eye Test", "Vaccination"],
}

LOCATIONS = {
    "meeting": ["Zoom", "Conference Room B", "3rd Floor Lounge", "Teams Call"],
    "workshop": ["Training Room 1", "Studio", "Auditorium", "Online Workshop"],
    "task": ["Desk", "Home Office", "Café"],
    "appointment": ["Downtown Clinic", "City Hospital", "Main Street Salon", "Banks Plaza"],
}


def build_events(days: int = 30, seed: int = 42) -> list[EventData]:
    rng = random.Random(seed)
    today = date.today()
    events: list[EventData] = []

    for d in range(days):
        day = today + timedelta(days=d)
        weekday = day.weekday()
        # weekend: 50% chance of a lighter day, weekdays denser
        n = rng.choice([0, 1, 1, 2, 2, 2, 3, 3]) if weekday < 5 else rng.choice([0, 0, 0, 1, 1])

        # deterministic-ish busy hours, spaced >=1h apart so the demo data is conflict-free
        hours = []
        for _ in range(n):
            hour = rng.randrange(9, 17)
            if all(abs(hour - h) >= 1 for h in hours):
                hours.append(hour)

        for hour in hours:
            category = rng.choice(list(TITLES.keys()))
            title = rng.choice(TITLES[category])
            start = f"{hour:02d}:{rng.choice(['00', '15', '30'])}"
            dur = rng.choice([30, 60, 60, 90])
            end = _add_minutes(start, dur)
            notes = rng.choice([
                "Bring the deck.", "Prepare questions first.", "",
                "Follow up afterwards.", "Client wants an update.", "",
                "Blocked — needs laptop.", "", "Monthly check-in.", "",
            ])
            events.append(EventData(
                title=title,
                event_date=day.isoformat(),
                start_time=start,
                end_time=end,
                category=category,  # type: ignore[arg-type]
                location=rng.choice(LOCATIONS[category]),
                notes=notes or None,
            ))

    # sort by date/time for deterministic ordering
    events.sort(key=lambda e: (e.event_date, e.start_time))
    return events


def _add_minutes(t: str, minutes: int) -> str:
    hh, mm = int(t[:2]), int(t[3:])
    total = hh * 60 + mm + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def seed_user(db: Session, user_id: str, force: bool = False) -> int:
    """Seed default onboarding events for the given user, using the given session.

    Every event created this way is flagged is_default=True so it can be told
    apart from events the user actually created, and bulk-removed later via
    remove_defaults(). Returns count created. No-op if the user already has
    events, unless force=True (which also wipes their existing events first —
    used by the CLI, not called from the web app).
    """
    count = db.scalar(select(func.count(Event.id)).where(Event.user_id == user_id))
    if count and not force:
        return int(count)

    if force:
        for e in db.scalars(select(Event).where(Event.user_id == user_id)).all():
            get_vectorstore().delete_event(e.id)
            db.delete(e)
        db.commit()

    vs = get_vectorstore()
    created = 0
    for data in build_events():
        try:
            ev = storage.add_event(db, user_id, data, is_default=True)
        except storage.ConflictError:
            continue  # skip the intentional overlap cleanly
        vs.index_event(ev.id, user_id, ev.title, ev.category, ev.event_date,
                       ev.start_time, ev.end_time, ev.notes)
        created += 1
    return created


def remove_defaults(db: Session, user_id: str) -> int:
    """Delete every auto-seeded default event for this user (SQL + vector index).

    User-created events (is_default=False) are never touched.
    """
    rows = db.scalars(
        select(Event).where(Event.user_id == user_id, Event.is_default.is_(True))
    ).all()
    vs = get_vectorstore()
    for e in rows:
        vs.delete_event(e.id)
        db.delete(e)
    db.commit()
    return len(rows)


def seed(user_id: str, force: bool = False) -> int:
    """CLI/standalone entry point: opens its own session. See seed_user()."""
    db = SessionLocal()
    try:
        return seed_user(db, user_id, force=force)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    if len(sys.argv) < 2:
        print("Usage: python -m app.seed <user_id> [--force]")
        sys.exit(1)
    user_id = sys.argv[1]
    force = "--force" in sys.argv
    n = seed(user_id, force=force)
    print(f"Seeded {n} events for user '{user_id}'.")
