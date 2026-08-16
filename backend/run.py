"""Entrypoint: python run.py  ->  serves API + frontend on http://127.0.0.1:8005"""
from __future__ import annotations

import uvicorn

from app.config import settings

if __name__ == "__main__":
    settings.ensure_dirs()
    print("=" * 60)
    print("  Synqra — Agentic RAG Schedule Assistant")
    print(f"  http://{settings.HOST}:{settings.PORT}")
    print("=" * 60)
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
