"""Agent tools: get_schedule and update_schedule.

Each tool exposes a JSON-schema definition (fed to the LLM for tool selection)
and an execute() bound to a specific user's data. All results are plain dicts /
strings so they can flow straight into the agent graph state.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import storage
from .google_calendar import enabled as gcal_enabled, sync as gcal_sync
from .humanize import humanize_date, humanize_range
from .rag import hybrid_retrieve, reindex_event, semantic_search, unindex_event
from .schemas import EventData, EventOut

# --------------------------------------------------------------------------- #
# Tool definitions (for the LLM)
# --------------------------------------------------------------------------- #
GET_SCHEDULE_TOOL = {
    "name": "get_schedule",
    "description": (
        "Retrieve the user's schedule events. Provide date_from/date_to (YYYY-MM-DD) for an exact "
        "date or range, and/or a natural-language query for semantic search (e.g. 'the dentist thing'). "
        "If a date was mentioned in the conversation, always pass it as date_from. Returns a list of events."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "End date YYYY-MM-DD (inclusive)"},
            "query": {"type": "string", "description": "Natural-language semantic query"},
        },
        "additionalProperties": False,
    },
}

UPDATE_SCHEDULE_TOOL = {
    "name": "update_schedule",
    "description": (
        "Add, update, or delete a schedule event for the user. "
        "action must be 'add', 'update', or 'delete'. "
        "For 'add'/'update' supply event_data {title, event_date (YYYY-MM-DD), start_time (HH:MM), "
        "end_time (HH:MM), category (meeting|workshop|task|appointment), location, notes}. "
        "For 'update'/'delete' you must already know the event_id — if you don't, call get_schedule first. "
        "The system refuses writes that overlap an existing event."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "update", "delete"]},
            "event_id": {"type": "string", "description": "id of the event to update/delete"},
            "event_data": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "event_date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "category": {"type": "string", "enum": ["meeting", "workshop", "task", "appointment"]},
                    "location": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}

TOOLS = [GET_SCHEDULE_TOOL, UPDATE_SCHEDULE_TOOL]


def tool_definitions() -> list[dict]:
    return TOOLS


# --------------------------------------------------------------------------- #
# Tool executors
# --------------------------------------------------------------------------- #
def execute_get_schedule(db: Session, user_id: str, args) -> dict:
    if not isinstance(args, dict):
        return {"ok": False, "message": "get_schedule arguments must be an object.", "events": [], "count": 0}
    date_from = args.get("date_from")
    date_to = args.get("date_to")
    query = args.get("query")
    if not date_from and not date_to and not query:
        # default: next 7 days so the agent never queries nothing
        date_from = date.today().isoformat()
        date_to = (date.today() + timedelta(days=7)).isoformat()
    events = hybrid_retrieve(db, user_id, date_from=date_from, date_to=date_to, query=query)
    return {"ok": True, "events": [_event_dict(e) for e in events], "count": len(events)}


def execute_update_schedule(db: Session, user_id: str, args) -> dict:
    """Add / update / delete an event. Never raises — the LLM controls `args`,
    so malformed input returns a structured message instead of a 500."""
    if not isinstance(args, dict):
        return {"ok": False, "message": "update_schedule arguments must be an object."}
    action = (args.get("action") or "").strip().lower()

    if action == "add":
        data = _parse_event_data(args.get("event_data"))
        if data is None:
            return {"ok": False, "message": "To add an event I need event_data with title, event_date, start_time and end_time."}
        try:
            ev = storage.add_event(db, user_id, data)
            reindex_event(user_id, ev)
            # Auto-sync to Google Calendar if connected
            if gcal_enabled():
                try:
                    gcal_sync(db, user_id, "push")
                except Exception:
                    pass  # Best-effort sync, don't fail the operation
            return {"ok": True, "message": f"Added '{ev.title}' on {humanize_date(ev.event_date)} {humanize_range(ev.start_time, ev.end_time)}.",
                    "events": [_event_dict(ev)]}
        except storage.ConflictError as ex:
            return {"ok": False, "conflict": True,
                    "message": "That time overlaps an existing event: " + _list_conflicts(ex.conflicting_events),
                    "conflicting_events": [_event_dict(e) for e in ex.conflicting_events]}
        except ValueError as ex:
            return {"ok": False, "message": str(ex)}

    if action == "update":
        event_id = args.get("event_id")
        if not event_id:
            return {"ok": False, "message": "An event_id is required to update — call get_schedule first."}
        data = _parse_event_data(args.get("event_data"))
        if data is None:
            return {"ok": False, "message": "To update an event I need event_data with title, event_date, start_time and end_time."}
        try:
            ev = storage.update_event(db, user_id, event_id, data)
            reindex_event(user_id, ev)
            # Auto-sync to Google Calendar if connected
            if gcal_enabled():
                try:
                    gcal_sync(db, user_id, "push")
                except Exception:
                    pass  # Best-effort sync, don't fail the operation
            return {"ok": True, "message": f"Updated '{ev.title}' to {humanize_date(ev.event_date)} {humanize_range(ev.start_time, ev.end_time)}.",
                    "events": [_event_dict(ev)]}
        except storage.NotFoundError:
            return {"ok": False, "message": "That event no longer exists."}
        except storage.ConflictError as ex:
            return {"ok": False, "conflict": True,
                    "message": "The new time overlaps an existing event: " + _list_conflicts(ex.conflicting_events),
                    "conflicting_events": [_event_dict(e) for e in ex.conflicting_events]}
        except ValueError as ex:
            return {"ok": False, "message": str(ex)}

    if action == "delete":
        event_id = args.get("event_id")
        if not event_id:
            return {"ok": False, "message": "An event_id is required to delete — call get_schedule first."}
        try:
            ev = storage.get_event(db, user_id, event_id)
            storage.delete_event(db, user_id, event_id)
            unindex_event(event_id)
            # Auto-sync to Google Calendar if connected
            if gcal_enabled():
                try:
                    gcal_sync(db, user_id, "push")
                except Exception:
                    pass  # Best-effort sync, don't fail the operation
            title = ev.title if ev else "Event"
            return {"ok": True, "message": f"Deleted '{title}'."}
        except storage.NotFoundError:
            return {"ok": False, "message": "That event no longer exists."}

    return {"ok": False, "message": f"Unknown action '{action}'. Use add, update, or delete."}


def _parse_event_data(event_data) -> EventData | None:
    """Build a validated EventData from LLM args, or None when they're unusable."""
    if not isinstance(event_data, dict):
        return None
    try:
        return EventData(**event_data)
    except (ValueError, TypeError, KeyError):
        return None


def _event_dict(e: EventOut) -> dict:
    d = e.model_dump()
    d.pop("similarity", None)
    return d


def _list_conflicts(events: list[EventOut]) -> str:
    return "; ".join(f"'{e.title}' ({humanize_date(e.event_date)} {humanize_range(e.start_time, e.end_time)})" for e in events)


# --------------------------------------------------------------------------- #
# Lookup helper used by the agent for disambiguation
# --------------------------------------------------------------------------- #
def find_candidate_events(db: Session, user_id: str, text: str, day: str | None = None) -> list[EventOut]:
    """Best-effort: find events matching a mention of title/type, optionally on a day."""
    base: list[EventOut]
    if day:
        base = storage.events_by_day(db, user_id, day)
    else:
        base = storage.upcoming_events(db, user_id, days=30)
    text_l = text.lower()
    scored = []
    for e in base:
        hay = f"{e.title} {e.category} {e.location or ''} {e.notes or ''}".lower()
        score = 0
        for tok in text_l.replace("?", "").split():
            if tok in hay:
                score += 1
        if score:
            scored.append((score, e))
    scored.sort(key=lambda t: (-t[0], t[1].start_time))
    return [e for _, e in scored]
