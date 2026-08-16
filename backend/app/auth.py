"""Authentication.

Session model: opaque random bearer tokens stored in the `sessions` table with an
expiry. user_id is ALWAYS derived from the verified token server-side — never from
a request body (same principle as the original n8n design, enforced in one place).

Google login: verifies the Google ID token against Google's tokeninfo endpoint and
checks the `aud` claim when GOOGLE_CLIENT_ID is configured.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import Session as SessionRow
from .models import User

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def create_session(db: Session, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_TTL_DAYS)
    db.add(SessionRow(token=token, user_id=user_id, expires_at=expires))
    db.commit()
    return token


def verify_google_id_token(id_token: str) -> dict:
    """Returns {sub, email, aud, exp, ...} from Google, or raises HTTPException."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Google login is not configured on this server")

    try:
        r = httpx.get(TOKENINFO_URL, params={"id_token": id_token}, timeout=15)
        body = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Could not reach Google token verification")

    if r.status_code != 200 or not body.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid Google token")

    if body.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token audience does not match this app")

    exp = body.get("exp")
    if exp and int(exp) * 1000 < datetime.now(timezone.utc).timestamp() * 1000:
        raise HTTPException(status_code=401, detail="Token expired")

    return body


def get_or_create_google_user(db: Session, info: dict) -> tuple[User, bool]:
    """Returns (user, is_new). Does NOT seed default events itself anymore —
    that used to run inline here and blocked the login response for new
    users (each seeded event gets embedded into ChromaDB, which is slow).
    The caller (routes/auth.py) is responsible for kicking off seeding as a
    background task using the returned is_new flag, so login always responds
    immediately regardless of whether this is someone's first sign-in."""
    user = db.scalar(select(User).where(User.id == info["sub"]))
    is_new = user is None
    if user is None:
        user = User(
            id=info["sub"],
            email=info.get("email", ""),
            display_name=info.get("name", info.get("email", "Google User")),
            auth_source="google",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        dirty = False
        if info.get("email") and user.email != info["email"]:
            user.email, dirty = info["email"], True
        if info.get("name") and user.display_name != info["name"]:
            user.display_name, dirty = info["name"], True
        if dirty:
            db.commit()
    return user, is_new


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <token> header")
    token = authorization.split(" ", 1)[1].strip()
    return _user_from_token(db, token)


def get_current_user_allow_query_token(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Same as get_current_user, but also accepts ?token=... in the URL.

    Only meant for the one route the browser's <audio> element hits directly
    (routes/voice.py's /tts/stream) — audio/video elements issue a plain GET
    and can't attach a custom Authorization header, so that's the only way to
    get real streaming playback (audio.src = url) instead of fetch+blob.
    """
    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1].strip()
    tok = bearer or token
    if not tok:
        raise HTTPException(status_code=401, detail="Missing session token")
    return _user_from_token(db, tok)


def _user_from_token(db: Session, token: str) -> User:
    row = db.scalar(select(SessionRow).where(SessionRow.token == token))
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired — please sign in again")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Session user no longer exists")
    return user
