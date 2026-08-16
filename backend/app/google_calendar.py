"""Google Calendar sync module (enabled when Google OAuth is configured).

Google stays the source of truth for event times; the app's SQLite + ChromaDB
remain the search/agent layer.

Flow:
  1. GET  /api/google/auth-url              -> consent URL for the current user
  2. GET  /api/google/callback?code=...      -> exchange code, store refresh token
  3. POST /api/google/sync {direction:push|pull}

Tokens are stored in data/google_tokens.json, encrypted with Fernet using
GOOGLE_TOKEN_KEY (a key file is generated on first use if the env var is empty).
This module is enabled when GOOGLE_CALENDAR_ENABLED=true and OAuth credentials are configured.
"""
from __future__ import annotations

import json
from pathlib import Path

from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from .config import settings
from .schemas import EventData

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

TOKEN_FILE = Path(settings.DATABASE_PATH).parent / "google_tokens.json"


# --------------------------------------------------------------------------- #
# Token encryption
# --------------------------------------------------------------------------- #
def _fernet() -> Fernet:
    if settings.GOOGLE_TOKEN_KEY:
        key = settings.GOOGLE_TOKEN_KEY.encode()
    else:
        key_file = Path(settings.DATABASE_PATH).parent / "google_token.key"
        if not key_file.exists():
            key_file.write_text(Fernet.generate_key().decode())
        key = key_file.read_text().strip().encode()
    return Fernet(key)


def _load_tokens() -> dict:
    if not TOKEN_FILE.exists():
        return {}
    try:
        raw = json.loads(TOKEN_FILE.read_text())
        return {uid: json.loads(_fernet().decrypt(raw[uid].encode()).decode()) for uid in raw}
    except Exception:
        return {}


def _save_tokens(tokens: dict) -> None:
    encrypted = {uid: _fernet().encrypt(json.dumps(tok).encode()).decode() for uid, tok in tokens.items()}
    TOKEN_FILE.write_text(json.dumps(encrypted))


def enabled() -> bool:
    return bool(settings.GOOGLE_CALENDAR_ENABLED and settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def _flow(redirect_uri: str) -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def auth_url(user_id: str, redirect_uri: str) -> str:
    flow = _flow(redirect_uri)
    url, _ = flow.authorization_url(access_type="offline", prompt="consent",
                                    state=user_id, include_granted_scopes="true")
    return url


def exchange_code(code: str, user_id: str, redirect_uri: str) -> bool:
    flow = _flow(redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials
    tokens = _load_tokens()
    tokens[user_id] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }
    _save_tokens(tokens)
    return True


def _creds(user_id: str) -> Credentials | None:
    tokens = _load_tokens()
    info = tokens.get(user_id)
    if not info:
        return None
    creds = Credentials(**{k: v for k, v in info.items() if v is not None})
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        info["token"] = creds.token
        _save_tokens({**tokens, user_id: info})
    return creds


def _service(user_id: str):
    creds = _creds(user_id)
    if creds is None:
        raise PermissionError("Google Calendar not connected for this user")
    return build("calendar", "v3", credentials=creds)


# --------------------------------------------------------------------------- #
# Sync
# --------------------------------------------------------------------------- #
def _to_event_data(cal_event: dict) -> EventData | None:
    try:
        start = cal_event.get("start", {}).get("dateTime")
        end = cal_event.get("end", {}).get("dateTime")
        if not start or not end:
            return None
        from datetime import datetime
        s = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone()
        e = datetime.fromisoformat(end.replace("Z", "+00:00")).astimezone()
        category = "meeting"
        text = (cal_event.get("summary") or "").lower()
        for c, words in {"task": ["task", "report", "deadline"], "appointment": ["appointment", "dentist", "doctor"],
                         "workshop": ["workshop", "training"]}.items():
            if any(w in text for w in words):
                category = c
                break
        return EventData(
            title=cal_event.get("summary") or "Untitled",
            event_date=s.date().isoformat(),
            start_time=s.strftime("%H:%M"),
            end_time=e.strftime("%H:%M"),
            category=category,  # type: ignore[arg-type]
            location=cal_event.get("location"),
            notes=cal_event.get("description"),
        )
    except Exception:
        return None


def _from_event(e) -> dict:
    return {
        "summary": e.title,
        "location": e.location,
        "description": e.notes,
        "start": {"dateTime": f"{e.event_date}T{e.start_time}:00"},
        "end": {"dateTime": f"{e.event_date}T{e.end_time}:00"},
    }


def sync(db, user_id: str, direction: str) -> dict:
    """direction: 'push' (local -> calendar) or 'pull' (calendar -> local)."""
    if not enabled():
        return {"pushed": 0, "pulled": 0, "errors": ["Google Calendar is not enabled on this server"]}
    from . import storage
    from .models import Event
    from .vectorstore import get_vectorstore

    service = _service(user_id)
    cal_id = "primary"
    pushed = pulled = 0
    errors: list[str] = []

    if direction == "push":
        events = storage.upcoming_events(db, user_id, days=365)
        for ev in events:
            try:
                if ev.google_event_id:
                    service.events().update(calendarId=cal_id, eventId=ev.google_event_id,
                                            body=_from_event(ev)).execute()
                else:
                    created = service.events().insert(calendarId=cal_id, body=_from_event(ev)).execute()
                    row = db.get(Event, ev.id)
                    if row:
                        row.google_event_id = created.get("id")
                        db.commit()
                pushed += 1
            except Exception as ex:
                errors.append(f"{ev.title}: {ex}")

    else:  # pull
        from datetime import date, timedelta
        tz = "UTC"
        now = datetime.now().astimezone()
        end = now + timedelta(days=365)
        try:
            items = service.events().list(
                calendarId=cal_id, timeMin=now.isoformat(), timeMax=end.isoformat(),
                singleEvents=True, orderBy="startTime", maxResults=500,
            ).execute().get("items", [])
        except Exception as ex:
            return {"pushed": 0, "pulled": 0, "errors": [f"list: {ex}"]}

        existing = {e.google_event_id: e for e in storage.upcoming_events(db, user_id, days=365) if e.google_event_id}
        for item in items:
            gid = item.get("id")
            data = _to_event_data(item)
            if not data:
                continue
            try:
                if gid in existing:
                    storage.update_event(db, user_id, existing[gid].id, data)
                else:
                    ev = storage.add_event(db, user_id, data)
                    row = db.get(Event, ev.id)
                    if row:
                        row.google_event_id = gid
                        db.commit()
                pulled += 1
            except Exception as ex:
                errors.append(f"{item.get('summary')}: {ex}")

    # reindex changed local events so semantic search stays current
    vs = get_vectorstore()
    for ev in storage.upcoming_events(db, user_id, days=365):
        vs.index_event(ev.id, user_id, ev.title, ev.category, ev.event_date,
                       ev.start_time, ev.end_time, ev.notes)

    return {"pushed": pushed, "pulled": pulled, "errors": errors}
