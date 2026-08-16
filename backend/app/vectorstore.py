"""ChromaDB persistent vector store for semantic search over a user's events.

The event's structured row lives in SQLite (source of truth); this store exists
ONLY to answer natural-language / semantic queries. Every record carries
user_id metadata so searches are always scoped to one user.
"""
from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions

from .config import settings
from .embeddings import event_embedding_text

_COLLECTION = "events"


class VectorStore:
    def __init__(self) -> None:
        settings.ensure_dirs()
        self._client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        self._ef = embedding_functions.ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        self._col = self._client.get_or_create_collection(
            name=_COLLECTION, metadata={"hnsw:space": "cosine"}, embedding_function=self._ef
        )

    def index_event(self, event_id: str, user_id: str, title: str, category: str,
                    event_date: str, start_time: str, end_time: str, notes: str | None = None) -> None:
        doc = event_embedding_text(title, category, event_date, start_time, end_time, notes)
        self._col.upsert(
            ids=[event_id],
            documents=[doc],
            metadatas=[{
                "user_id": user_id,
                "title": title,
                "category": category,
                "event_date": event_date,
                "start_time": start_time,
                "end_time": end_time,
                "notes": notes or "",
            }],
        )

    def delete_event(self, event_id: str) -> None:
        try:
            self._col.delete(ids=[event_id])
        except Exception:
            pass  # id may not exist in the vector store

    def search(self, query: str, user_id: str, top_k: int = 5) -> list[dict]:
        """Return top-k matches scoped to user_id with similarity scores."""
        res = self._col.query(
            query_texts=[query],
            n_results=top_k,
            where={"user_id": user_id},
            include=["documents", "metadatas", "distances"],
        )
        out: list[dict] = []
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for i, mid in enumerate(ids):
            meta = metas[i] or {}
            sim = 1.0 - float(dists[i]) if i < len(dists) else 0.0
            out.append({
                "id": mid,
                "title": meta.get("title", docs[i] if i < len(docs) else ""),
                "event_date": meta.get("event_date", ""),
                "start_time": meta.get("start_time", ""),
                "end_time": meta.get("end_time", ""),
                "category": meta.get("category", ""),
                "notes": meta.get("notes", ""),
                "location": meta.get("location", ""),
                "similarity": round(max(0.0, sim), 4),
            })
        return out

    def count(self) -> int:
        return self._col.count()


_vs: VectorStore | None = None


def get_vectorstore() -> VectorStore:
    global _vs
    if _vs is None:
        _vs = VectorStore()
    return _vs
