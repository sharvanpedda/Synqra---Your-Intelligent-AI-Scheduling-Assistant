"""SQLAlchemy engine + session factory for the SQLite source-of-truth store."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def make_engine():
    # check_same_thread=False so the same engine can be used from FastAPI's
    # threadpool + the reminder scheduler + background tasks.
    settings.data_dir()
    return create_engine(
        f"sqlite:///{settings.DATABASE_PATH}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
