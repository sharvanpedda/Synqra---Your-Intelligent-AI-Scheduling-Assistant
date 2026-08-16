"""Pydantic schemas — wire format for every endpoint."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CATEGORIES = ("meeting", "workshop", "task", "appointment")
Category = Literal["meeting", "workshop", "task", "appointment"]


class EventData(BaseModel):
    """Payload for creating/updating an event."""
    title: str = Field(min_length=1, max_length=255)
    event_date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str    # HH:MM
    category: Category = "meeting"
    location: str | None = None
    notes: str | None = None

    @field_validator("event_date")
    @classmethod
    def _date(cls, v: str) -> str:
        if len(v) != 10 or v[4] != "-" or v[7] != "-":
            raise ValueError("event_date must be YYYY-MM-DD")
        try:
            from datetime import date as _d
            _d.fromisoformat(v)
        except ValueError:
            raise ValueError("event_date must be a valid date (YYYY-MM-DD)")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def _time(cls, v: str) -> str:
        if len(v) != 5 or v[2] != ":":
            raise ValueError("time must be HH:MM (24h)")
        try:
            hh, mm = int(v[:2]), int(v[3:])
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
        except ValueError:
            raise ValueError("time must be a valid HH:MM")
        return v

    def check_order(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")


class EventOut(EventData):
    id: str
    source: str = "local"
    google_event_id: str | None = None
    is_default: bool = False  # auto-seeded onboarding event, not user-created
    similarity: float | None = None  # present for semantic search results


class LoginGoogle(BaseModel):
    id_token: str = Field(min_length=10)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    auth_source: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatTurn] = []


class ToolCallOut(BaseModel):
    name: str
    args: dict


class AgentResponse(BaseModel):
    reply: str
    intent: str = "chat"
    tool_calls: list[ToolCallOut] = []
    events: list[EventOut] = []


class FreeSlot(BaseModel):
    start: str
    end: str


class DashboardOut(BaseModel):
    today: list[EventOut] = []
    conflicts: list[list[EventOut]] = []
    upcoming: list[EventOut] = []
    schedule_30d: list[EventOut] = []  # today through +30 days, for the consolidated dashboard view
    free_slots_today: list[FreeSlot] = []
    has_default_events: bool = False


class HealthOut(BaseModel):
    status: str
    llm_provider: str
    llm_connected: bool
    rag_indexed: int
    auth: str


class GoogleSyncIn(BaseModel):
    direction: Literal["push", "pull"] = "pull"


class GoogleSyncOut(BaseModel):
    pushed: int = 0
    pulled: int = 0
    errors: list[str] = []


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
