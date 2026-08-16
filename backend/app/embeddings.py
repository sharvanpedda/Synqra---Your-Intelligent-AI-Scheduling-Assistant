"""Local, offline, FREE embeddings via ChromaDB's built-in ONNX MiniLM embedder.

No API key, no network call, no cost. all-MiniLM-L6-v2 gives 384-dim vectors that
are perfectly adequate for schedule-document retrieval.
"""
from __future__ import annotations

import chromadb.utils.embedding_functions as embedding_functions

from .config import settings


class Embedder:
    def __init__(self) -> None:
        self._fn = embedding_functions.ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._fn(texts)  # type: ignore[operator]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


def event_embedding_text(title: str, category: str, event_date: str, start_time: str,
                         end_time: str, notes: str | None = None) -> str:
    n = f" {notes}" if notes else ""
    return f"{title} — a {category} on {event_date} from {start_time} to {end_time}.{n}"


def event_embedding_text_from_dict(e: dict) -> str:
    return event_embedding_text(
        e["title"], e["category"], e["event_date"], e["start_time"], e["end_time"], e.get("notes")
    )


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def embed(text: str) -> list[float]:
    return get_embedder().embed_one(text)


def embed_many(texts: list[str]) -> list[list[float]]:
    return get_embedder().embed(texts)
