"""Human-friendly date/time formatting for anything the agent says out loud
or types in chat.

Internal storage/API stays ISO ('YYYY-MM-DD') and 24-hour ('HH:MM') —
these helpers are presentation-only, used when building the `reply` /
`message` strings that get spoken by TTS or shown in the chat widget.

Rules (per product decision):
  * Times are always 12-hour with AM/PM ("2:00 PM"), never 24-hour.
  * Dates are "<day> <month>" ("15 August") with NO year, since the year
    is almost always the current one and saying it every time is noisy —
    UNLESS the date falls in a different year than today, in which case
    the year is included ("15 August 2027") so it's unambiguous.
"""
from __future__ import annotations

from datetime import date

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def humanize_date(iso_date: str | None) -> str:
    """'2026-08-15' -> '15 August' (current year) or '15 August 2027' (other years)."""
    if not iso_date:
        return ""
    try:
        y, m, d = (int(p) for p in iso_date.split("-"))
        dt = date(y, m, d)
    except (ValueError, TypeError):
        return iso_date
    month = _MONTHS[dt.month - 1]
    if dt.year == date.today().year:
        return f"{dt.day} {month}"
    return f"{dt.day} {month} {dt.year}"


def humanize_time(hhmm: str | None) -> str:
    """'14:00' -> '2:00 PM'. '09:05' -> '9:05 AM'."""
    if not hhmm:
        return ""
    try:
        h, m = (int(p) for p in hhmm.split(":"))
    except (ValueError, TypeError):
        return hhmm
    meridiem = "AM" if h < 12 else "PM"
    hour = h % 12 or 12
    return f"{hour}:{m:02d} {meridiem}"


def humanize_range(start_hhmm: str | None, end_hhmm: str | None) -> str:
    """('14:00','15:30') -> '2:00 PM–3:30 PM'."""
    return f"{humanize_time(start_hhmm)}\u2013{humanize_time(end_hhmm)}"
