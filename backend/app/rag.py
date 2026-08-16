"""Hybrid retrieval (RAG).

Two retrieval paths, both user-scoped:
  * structured — exact date/range/category lookups straight from SQLite
  * semantic   — ChromaDB cosine search over embeddings for natural-language queries
                (e.g. "when is my dentist thing", "the workshop about slides")

The `retrieve()` helper used by the agent tries structured first when dates are
given, and augments with semantic results when a free-text query is present.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from . import storage
from .schemas import EventOut
from .vectorstore import get_vectorstore


def semantic_search(db: Session, user_id: str, query: str, top_k: int = 5) -> list[EventOut]:
    hits = get_vectorstore().search(query, user_id, top_k=top_k)
    out: list[EventOut] = []
    for h in hits:
        try:
            out.append(EventOut(**h))
        except Exception:
            continue
    return out


def reindex_event(user_id: str, ev: EventOut) -> None:
    """Keep Chroma in sync after any write (agent tools, fallback, REST)."""
    get_vectorstore().index_event(
        ev.id, user_id, ev.title, ev.category, ev.event_date, ev.start_time, ev.end_time, ev.notes
    )


def unindex_event(event_id: str) -> None:
    """Remove an event from Chroma after deletion."""
    get_vectorstore().delete_event(event_id)


def hybrid_retrieve(db: Session, user_id: str, date_from: str | None = None,
                    date_to: str | None = None, category: str | None = None,
                    query: str | None = None, top_k: int = 5) -> list[EventOut]:
    """Returns structured results (by range) plus semantic results (by query).

    Deduplicates by event id. Structured results take priority when both present.
    """
    results: dict[str, EventOut] = {}

    if date_from or date_to:
        # default range: today .. today+30 (mirrors the frontend "next 30 days")
        if not date_from:
            date_from = _today()
        if not date_to:
            date_to = _today_plus(30)
        for e in storage.list_events(db, user_id, date_from, date_to, category):
            results[e.id] = e

    if query:
        for e in semantic_search(db, user_id, query, top_k=top_k):
            results.setdefault(e.id, e)

    return sorted(results.values(), key=lambda e: (e.event_date, e.start_time))


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


def _today_plus(days: int) -> str:
    from datetime import date, timedelta
    return (date.today() + timedelta(days=days)).isoformat()
