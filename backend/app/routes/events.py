"""Event CRUD + semantic search routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import storage
from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..rag import semantic_search
from ..schemas import EventData, EventOut
from ..seed import remove_defaults
from ..vectorstore import get_vectorstore

router = APIRouter(prefix="/api/events", tags=["events"])


def _conflict_409(ex: storage.ConflictError):
    return HTTPException(
        status_code=409,
        detail={"error": "conflict", "conflicting_events": [e.model_dump() for e in ex.conflicting_events]},
    )


@router.get("", response_model=list[EventOut])
def list_events(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    category: str | None = Query(default=None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import date, timedelta
    f = date_from or date.today().isoformat()
    t = date_to or (date.today() + timedelta(days=30)).isoformat()
    return storage.list_events(db, user.id, f, t, category)


@router.get("/today", response_model=list[EventOut])
def today(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return storage.events_today(db, user.id)


@router.get("/search", response_model=list[EventOut])
def search(q: str = Query(min_length=1), user=Depends(get_current_user), db: Session = Depends(get_db)):
    return semantic_search(db, user.id, q, top_k=5)


# NOTE: this must stay ABOVE the "/{event_id}" routes below — FastAPI matches
# routes in declaration order, and "/{event_id}" would otherwise swallow
# "/defaults" as a literal event id.
@router.delete("/defaults", response_model=dict)
def delete_default_events(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove every auto-seeded default event for the current user. Events the
    user created themselves are never touched."""
    removed = remove_defaults(db, user.id)
    return {"removed": removed}


@router.post("", response_model=EventOut, status_code=201)
def add_event(body: EventData, user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        ev = storage.add_event(db, user.id, body)
    except storage.ConflictError as ex:
        raise _conflict_409(ex)
    except ValueError as ex:
        raise HTTPException(status_code=422, detail=str(ex))
    get_vectorstore().index_event(ev.id, user.id, ev.title, ev.category, ev.event_date,
                                  ev.start_time, ev.end_time, ev.notes)
    return ev


@router.put("/{event_id}", response_model=EventOut)
def update_event(event_id: str, body: EventData, user=Depends(get_current_user),
                 db: Session = Depends(get_db)):
    try:
        ev = storage.update_event(db, user.id, event_id, body)
    except storage.NotFoundError:
        raise HTTPException(status_code=404, detail="Event not found")
    except storage.ConflictError as ex:
        raise _conflict_409(ex)
    except ValueError as ex:
        raise HTTPException(status_code=422, detail=str(ex))
    get_vectorstore().index_event(ev.id, user.id, ev.title, ev.category, ev.event_date,
                                  ev.start_time, ev.end_time, ev.notes)
    return ev


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        storage.delete_event(db, user.id, event_id)
    except storage.NotFoundError:
        raise HTTPException(status_code=404, detail="Event not found")
    get_vectorstore().delete_event(event_id)
    return None
