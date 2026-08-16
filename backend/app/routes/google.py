"""Google Calendar OAuth + sync routes.

The OAuth `state` param is never trusted as a user id. On /auth-url we mint a
random nonce bound to the *authenticated* user (in-process, with a TTL); the
callback only exchanges a code for the user whose nonce it can prove it owns.
An attacker who runs their own OAuth flow cannot bind tokens to a victim's
user_id, because they can't forge the nonce.
"""
from __future__ import annotations

import secrets
import time
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..google_calendar import auth_url, enabled, exchange_code, sync as run_sync
from ..schemas import GoogleSyncIn, GoogleSyncOut

router = APIRouter(prefix="/api/google", tags=["google"])

# nonce -> (user_id, expires_at). Process-local is fine: a stale flow simply
# requires the user to re-click "Connect" after a restart.
_pending: dict[str, tuple[str, float]] = {}
_pending_lock = Lock()
NONCE_TTL_SECONDS = 600  # consent window: 10 minutes


def _issue_nonce(user_id: str) -> str:
    nonce = secrets.token_urlsafe(24)
    with _pending_lock:
        _pending[nonce] = (user_id, time.monotonic() + NONCE_TTL_SECONDS)
    return nonce


def _consume_nonce(nonce: str) -> str | None:
    """Return the user_id bound to this nonce, or None if unknown/expired."""
    with _pending_lock:
        entry = _pending.pop(nonce, None)
    if entry and entry[1] > time.monotonic():
        return entry[0]
    return None


def _redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/google/callback"


@router.get("/auth-url")
def get_auth_url(request: Request, user=Depends(get_current_user)):
    if not enabled():
        raise HTTPException(status_code=400, detail="Google Calendar is not enabled on this server")
    return {"url": auth_url(_issue_nonce(user.id), _redirect_uri(request))}


@router.get("/callback")
def callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    if not enabled():
        raise HTTPException(status_code=400, detail="Google Calendar is not enabled on this server")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    user_id = _consume_nonce(state)
    if user_id is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired authorization state. Please start Google Calendar setup again.",
        )
    exchange_code(code, user_id, _redirect_uri(request))
    return {"ok": True, "connected": True}


@router.post("/sync", response_model=GoogleSyncOut)
def sync(body: GoogleSyncIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not enabled():
        raise HTTPException(status_code=400, detail="Google Calendar is not enabled on this server")
    result = run_sync(db, user.id, body.direction)
    return GoogleSyncOut(**result)
