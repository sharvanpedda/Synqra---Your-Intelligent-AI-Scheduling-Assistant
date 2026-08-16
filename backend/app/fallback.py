"""Deterministic intent parser — the no-LLM safety net.

When no LLM is reachable (no Ollama, no free API key), the agent graph still runs
end-to-end using this module for intent classification, date/time resolution, and
reply composition. It covers the canonical query shapes:

  * "What do I have scheduled tomorrow?"           -> schedule query
  * "Am I free Friday afternoon?"                  -> free-check
  * "Add a meeting on August 15 at 3 PM."          -> add
  * "Move my meeting from 2 PM to 4 PM."           -> update (with disambiguation)
  * "Delete my client call on Friday"              -> delete

Heuristics are intentionally conservative: when in doubt it asks a clarifying
question instead of guessing.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from . import storage, tools
from .humanize import humanize_date, humanize_range, humanize_time
from .rag import reindex_event, semantic_search, unindex_event
from .schemas import EventData, EventOut

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
CATEGORY_WORDS = {
    "meeting": ["meeting", "sync", "standup", "1:1", "one-on-one", "call", "review", "interview", "huddle", "retro"],
    "workshop": ["workshop", "bootcamp", "training", "seminar", "session", "deep dive", "hackathon"],
    "task": ["task", "report", "review pr", "portfolio", "slides", "deadline", "chore", "errand", "submit"],
    "appointment": ["appointment", "dentist", "doctor", "checkup", "haircut", "bank", "clinic", "physio", "therapy"],
}


# --------------------------------------------------------------------------- #
# Intent classification
# --------------------------------------------------------------------------- #
def classify_intent(message: str) -> str:
    """Returns one of: query_schedule | add | update | delete | free_check | chat"""
    m = message.lower()
    is_freeish = bool(re.search(r"\b(free|available|busy|booked|open)\b", m) or "am i free" in m)

    # A leading question word means a query, not a command — so
    # "what appointment did I just add?" is a lookup, not an add.
    # "you"/"please" signal the user is addressing the assistant ("can you add...?").
    if re.match(r"^(what|when|which|where|who|how|why|is|are|was|were|do|does|did|"
                r"can|could|should|may|would)\b", m) and "you" not in m and "please" not in m:
        return "free_check" if is_freeish else "query_schedule"

    if re.search(r"\b(add|create|schedule|book|set up|plan|put)\b", m) and re.search(
            r"\b(meeting|appointment|workshop|task|call|event|session)\b", m):
        return "add"
    if re.search(r"\b(move|reschedule|reschedule to|change|shift|push)\b", m):
        return "update"
    if re.search(r"\b(delete|cancel|remove|drop|clear)\b", m):
        return "delete"
    if is_freeish:
        return "free_check"
    if re.search(r"\b(what|when|which|where|who|list|show|tell me|upcoming|schedule)\b", m):
        return "query_schedule"
    if _extract_date(m) or _extract_time(m):
        return "query_schedule"
    return "chat"


# --------------------------------------------------------------------------- #
# Date / time extraction
# --------------------------------------------------------------------------- #
def _extract_date(text: str) -> str | None:
    """Return 'YYYY-MM-DD' for any date mentioned, or None."""
    t = text.lower()
    today = date.today()

    if "today" in t or "tonight" in t:
        return today.isoformat()
    if "tomorrow" in t:
        return (today + timedelta(days=1)).isoformat()
    if "day after tomorrow" in t:
        return (today + timedelta(days=2)).isoformat()
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat()

    # weekday names ("friday", "this friday", "next friday")
    for i, name in enumerate(WEEKDAYS):
        if name in t:
            delta = (i - today.weekday()) % 7
            if "next" in t:
                delta = delta + 7 if delta > 0 else delta + 7
            elif delta == 0:
                delta = 0 if "this" in t or "on" in t else 0
            return (today + timedelta(days=delta)).isoformat()

    # "august 15", "aug 15", "august 15th", "august 15 2027", "aug 15th, 2027"
    mm = re.search(r"\b([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b", t)
    if mm and mm.group(1) in MONTHS:
        month = MONTHS[mm.group(1)]
        day = int(mm.group(2))
        explicit_year = mm.group(3)
        year = int(explicit_year) if explicit_year else today.year
        try:
            d = date(year, month, day)
            # only roll forward to next year when the user didn't say a year themselves
            if not explicit_year and d < today:
                d = date(year + 1, month, day)
            return d.isoformat()
        except ValueError:
            return None

    # "15 august", "15th aug", "15 august 2027", "15th aug, 2027" (day before month)
    mm = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\.?(?:,?\s+(\d{4}))?\b", t)
    if mm and mm.group(2) in MONTHS:
        day = int(mm.group(1))
        month = MONTHS[mm.group(2)]
        explicit_year = mm.group(3)
        year = int(explicit_year) if explicit_year else today.year
        try:
            d = date(year, month, day)
            if not explicit_year and d < today:
                d = date(year + 1, month, day)
            return d.isoformat()
        except ValueError:
            return None

    # "on the 15th" / "on the 5th" -> next occurrence of that day-of-month
    mm = re.search(r"\bon the (\d{1,2})(?:st|nd|rd|th)\b", t)
    if mm:
        day = int(mm.group(1))
        for i in range(0, 45):
            d = today + timedelta(days=i)
            if d.day == day:
                return d.isoformat()
        return None

    return None


def _extract_time(text: str) -> tuple[str, str] | None:
    """Return (start 'HH:MM', end 'HH:MM') for a range/point time, or None.

    Handles '2 PM', '2pm', '14:00', 'from 2 to 4 PM', '3 to 4pm', 'at 3'.
    """
    t = text.lower()
    out_start: str | None = None
    out_end: str | None = None

    def to_24h(hh: int, meridiem: str | None) -> str:
        if meridiem == "am":
            return f"{hh % 12:02d}:00"
        if meridiem == "pm":
            return f"{(hh % 12) + 12:02d}:00"
        return f"{hh:02d}:00" if hh < 24 else "23:00"

    # full range: "from 2 pm to 4 pm" / "2 to 4 PM" / "14:00-16:00"
    m = re.search(r"(?:from\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\s*(?:-|to|until|till)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", t)
    if m:
        h1, m1, p1, h2, m2, p2 = m.groups()
        # a shared trailing meridiem ("from 2 to 4 PM") applies to both ends
        out_start = _fmt(int(h1), int(m1 or 0), _mer(p1 or p2))
        out_end = _fmt(int(h2), int(m2 or 0), _mer(p2 or p1))
        return (out_start, out_end)

    # point time with meridiem: "3 pm", "3pm", "3 p.m."
    m = re.search(r"(?:at\s+|@)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", t)
    if m:
        h, mi, p = m.groups()
        out_start = _fmt(int(h), int(mi or 0), _mer(p))
        out_end = _shift(out_start, 60)
        return (out_start, out_end)

    # 24h "15:00"
    m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t)
    if m:
        out_start = _fmt(int(m.group(1)), int(m.group(2)), None)
        out_end = _shift(out_start, 60)
        return (out_start, out_end)

    # bare "at 3" or "at 4"
    m = re.search(r"\bat (\d{1,2})\b", t)
    if m:
        out_start = _fmt(int(m.group(1)), 0, None)
        out_end = _shift(out_start, 60)
        return (out_start, out_end)

    return None


def _mer(p: str | None) -> str | None:
    if not p:
        return None
    return p.rstrip(".").lower()


def _fmt(h: int, m: int, meridiem: str | None) -> str:
    if meridiem:
        h = h % 12 + (12 if meridiem == "pm" else 0)
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    return f"{h:02d}:{m:02d}"


def _shift(t: str, minutes: int) -> str:
    hh, mm = int(t[:2]), int(t[3:])
    total = hh * 60 + mm + minutes
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"


def extract_category(text: str) -> str | None:
    t = text.lower()
    for cat, words in CATEGORY_WORDS.items():
        for w in words:
            if w in t:
                return cat
    return None


# --------------------------------------------------------------------------- #
# Main fallback entrypoint (mirrors the agent graph's job)
# --------------------------------------------------------------------------- #
def run_fallback(db: Session, user_id: str, message: str,
                 tool_results: dict | None = None) -> dict:
    """Executes the whole turn deterministically. Returns an AgentResponse-shaped dict.

    `tool_results` lets a prior (LLM-driven) tool call be folded into the reply if
    the LLM went silent mid-turn.
    """
    intent = classify_intent(message)
    day = _extract_date(message)
    times = _extract_time(message)

    # --- ADD --- #
    if intent == "add":
        if not day:
            return _clarify("Which day? I didn't catch a date (say 'tomorrow' or a specific date like '15 August').")
        cat = extract_category(message) or "meeting"
        title = _infer_title(message)
        if title in ("Event", ""):
            title = cat.title()  # e.g. "Meeting", "Dentist Appointment" not possible -> category default
        start, end = times or ("09:00", "10:00")
        data = EventData(title=title, event_date=day, start_time=start, end_time=end, category=cat)  # type: ignore[arg-type]
        try:
            ev = storage.add_event(db, user_id, data)
            reindex_event(user_id, ev)
            return _ok("add", ev, f"Done — added '{ev.title}' for {humanize_date(day)} at {humanize_range(start, end)}.", [ev])
        except storage.ConflictError as ex:
            clash = _fmt_clashes(ex.conflicting_events)
            return _ok("add", None,
                       f"That time conflicts with {clash}. Want me to pick another time?", [])
        except ValueError as ex:
            return _clarify(f"I couldn't do that: {ex}")

    # --- DELETE --- #
    if intent == "delete":
        if not day:
            day = date.today().isoformat()
        title = _infer_title(message)
        matches = _find(db, user_id, title, day, message)
        if not matches:
            return _ok("delete", None, f"I couldn't find {'anything' if not title else f"an event like '{title}'"} on {humanize_date(day)}.", [])
        if len(matches) == 1:
            ev = matches[0]
            storage.delete_event(db, user_id, ev.id)
            unindex_event(ev.id)
            return _ok("delete", ev, f"Deleted '{ev.title}' ({humanize_range(ev.start_time, ev.end_time)}).", [ev])
        names = ", ".join(f"'{e.title}' ({humanize_time(e.start_time)})" for e in matches[:4])
        return _clarify(f"Which one? I see: {names}.")

    # --- UPDATE (move/reschedule) --- #
    if intent == "update":
        if not day:
            day = date.today().isoformat()
        if not times:
            return _clarify("What time should I move it to? (e.g. 'move it to 4 PM')")
        title = _infer_title(message)
        matches = _find(db, user_id, title, day, message)
        if not matches:
            return _ok("update", None, f"I couldn't find an event like '{title}' on {humanize_date(day)}.", [])
        if len(matches) == 1:
            ev = matches[0]
            data = EventData(title=ev.title, event_date=ev.event_date, start_time=times[0],
                             end_time=times[1], category=ev.category, location=ev.location, notes=ev.notes)  # type: ignore[arg-type]
            try:
                upd = storage.update_event(db, user_id, ev.id, data)
                reindex_event(user_id, upd)
                return _ok("update", upd, f"Moved '{upd.title}' to {humanize_range(times[0], times[1])}.", [upd])
            except storage.ConflictError as ex:
                return _ok("update", None,
                           f"The new time overlaps {_fmt_clashes(ex.conflicting_events)}.", [])
            except storage.NotFoundError:
                return _ok("update", None, "That event no longer exists.", [])
        names = ", ".join(f"'{e.title}' ({humanize_time(e.start_time)})" for e in matches[:4])
        return _clarify(f"Which one? I see: {names}.")

    # --- FREE CHECK --- #
    if intent == "free_check":
        day = day or date.today().isoformat()
        events = storage.events_by_day(db, user_id, day)
        if times:
            overlap = [e for e in events
                       if _ovl(times[0], times[1], e.start_time, e.end_time)]
            if overlap:
                busy = ", ".join(f"'{e.title}' ({humanize_range(e.start_time, e.end_time)})" for e in overlap)
                return _ok("free_check", None, f"You're busy {humanize_date(day)} {humanize_range(times[0], times[1])}: {busy}.", events)
            return _ok("free_check", None, f"You're free on {humanize_date(day)} between {humanize_time(times[0])} and {humanize_time(times[1])}.", events)
        if events:
            line = "You have: " + "; ".join(f"'{e.title}' {humanize_range(e.start_time, e.end_time)}" for e in events)
            return _ok("free_check", None, line, events)
        return _ok("free_check", None, f"Nothing on the books for {humanize_date(day)}.", events)

    # --- QUERY --- #
    if intent == "query_schedule":
        if day:
            events = storage.events_by_day(db, user_id, day)
        elif re.search(r"\b(this|next|coming|upcoming) week\b", message.lower()):
            events = storage.upcoming_events(db, user_id, days=7)
        else:
            events = semantic_search(db, user_id, message, top_k=5)
        if not events:
            return _ok("query_schedule", None,
                       f"I couldn't find any events{ f' on {humanize_date(day)}' if day else ' matching that'}.",
                       [])
        if day:
            line = " on " + humanize_date(day) if day else ""
            detail = "; ".join(f"'{e.title}' {humanize_range(e.start_time, e.end_time)}" for e in events)
            return _ok("query_schedule", None, f"Here's your schedule{line}: {detail}.", events)
        detail = "; ".join(f"'{e.title}' {humanize_date(e.event_date)} {humanize_time(e.start_time)}" for e in events)
        return _ok("query_schedule", None, f"Here's what I found: {detail}.", events)

    # --- CHAT (greeting / general) --- #
    return _ok("chat", None, _chat_reply(message), [])


def _ovl(a_s, a_e, b_s, b_e) -> bool:
    return a_s < b_e and a_e > b_s


def _infer_title(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\b(add|create|schedule|book|move|reschedule|change|delete|cancel|remove|my|the|a|an)\b", " ", t)
    t = re.sub(r"\b(from|to|at|on|for|until|till|at)\b", " ", t)
    t = re.sub(r"\b(meeting|appointment|workshop|task)\b", "", t)
    t = re.sub(r"\d{1,2}(:\d{2})?\s*(am|pm)?\b", "", t)
    t = re.sub(r"\b\d{1,2}(st|nd|rd|th)\b", "", t)
    t = re.sub(r"\b[a-z]+(?: \d{1,2})?\b", "", t)  # drop leftover weekdays/months
    t = re.sub(r"[^a-zA-Z0-9 ]+", " ", t)          # drop punctuation, periods, quotes
    return " ".join(t.split()).title() or "Event"


def _find(db: Session, user_id: str, title: str, day: str, message: str) -> list[EventOut]:
    if title and title != "Event":
        hits = tools.find_candidate_events(db, user_id, title, day)
        if hits:
            return hits
    # fall back to semantic search for fuzzy titles
    return semantic_search(db, user_id, message, top_k=3)


def _fmt_clashes(events: list[EventOut]) -> str:
    return "; ".join(f"'{e.title}' ({humanize_range(e.start_time, e.end_time)})" for e in events)


def _chat_reply(message: str) -> str:
    m = message.lower().strip()
    if any(g in m for g in ["hi", "hello", "hey", "good morning", "good afternoon"]):
        return "Hello! Ask me about your schedule — 'what's tomorrow look like?', 'am I free Friday?', or 'add a meeting on August 15 at 3 PM'."
    if "help" in m or "?" in m and "schedule" in m:
        return ("I can look up your schedule, check free time, and add/move/delete events. "
                "Try: 'what do I have tomorrow?', 'am I free Friday afternoon?', "
                "'add a dentist appointment on the 20th at 10am', or 'move my meeting to 4 PM'.")
    return "I can look up your schedule, check free time, and add/move/delete events — just ask in plain words."


# canonical tool names surfaced to the frontend / history
_TOOL_FOR_INTENT = {
    "add": "update_schedule",
    "update": "update_schedule",
    "delete": "update_schedule",
    "query_schedule": "get_schedule",
    "free_check": "get_schedule",
}


def _ok(intent: str, ev: EventOut | None, reply: str, events: list[EventOut]) -> dict:
    if ev:
        tool = _TOOL_FOR_INTENT.get(intent, intent)
        args = {"action": intent} if tool == "update_schedule" else {}
        tool_calls = [{"name": tool, "args": args}]
    else:
        tool_calls = []
    return {
        "reply": reply,
        "intent": intent,
        "tool_calls": tool_calls,
        "events": [_event_dict(e) for e in events],
    }


def _clarify(reply: str) -> dict:
    return {"reply": reply, "intent": "chat", "tool_calls": [], "events": []}


def _event_dict(e: EventOut) -> dict:
    d = e.model_dump()
    d.pop("similarity", None)
    return d
