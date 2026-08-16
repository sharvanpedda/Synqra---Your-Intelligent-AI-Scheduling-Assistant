"""SSE notification stream + test endpoint.

Browser EventSource cannot set Authorization headers, so the token is passed as a
query parameter and verified server-side exactly like the header path.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import Session as SessionRow
from ..notifications import hub

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _user_from_token(token: str, db: Session) -> str | None:
    if not token:
        return None
    row = db.scalar(select(SessionRow).where(SessionRow.token == token))
    return row.user_id if row else None


@router.get("/stream")
async def stream(token: str = "", db: Session = Depends(get_db)):
    user_id = _user_from_token(token, db)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    q = await hub.subscribe(user_id)

    async def gen():
        try:
            # immediate hello so the client knows the stream is live
            yield f"event: hello\ndata: {json.dumps({'ok': True})}\n\n"
            while True:
                try:
                    event_type, payload = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"event: {event_type}\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # comment keeps proxies/EventSource alive
        finally:
            await hub.unsubscribe(user_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/test", status_code=200)
async def test_notification(user=Depends(get_current_user)):
    from datetime import datetime
    await hub.broadcast(user.id, "reminder", {
        "event": {"title": "Test Reminder", "start_time": datetime.now().strftime("%H:%M")},
        "message": "This is a test notification from the server.",
    })
    return {"ok": True}
