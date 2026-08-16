"""Agent route — the single endpoint text chat AND voice use."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import agent
from ..auth import get_current_user
from ..database import get_db
from ..schemas import AgentRequest, AgentResponse

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("", response_model=AgentResponse)
def ask(body: AgentRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    t0 = time.monotonic()
    history = [{"role": t.role, "content": t.content} for t in body.history]
    result = agent.run_agent(db, user.id, body.message, history)
    print(f"[agent] turn took {time.monotonic() - t0:.2f}s "
          f"({len(result.get('tool_calls', []))} tool call(s))")
    return AgentResponse(
        reply=result.get("reply", ""),
        intent=result.get("intent", "chat"),
        tool_calls=result.get("tool_calls", []),
        events=result.get("events", []),
    )
