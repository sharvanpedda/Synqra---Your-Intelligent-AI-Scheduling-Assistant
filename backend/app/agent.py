"""LangGraph agent — the "agentic RAG" core.

A StateGraph with a genuine tool-calling loop:

    route_intent -> resolve_dates -> retrieve (RAG) -> decide
                                                       |  (tool_call) -> execute_tool -> decide (loop, max N)
                                                       |  (answer / clarify) -> finalize

* `retrieve` grounds the agent in the user's real schedule (hybrid RAG: exact
  date lookups + semantic search over ChromaDB embeddings).
* `decide` is an LLM node that emits a JSON decision: call `get_schedule` or
  `update_schedule`, answer directly, or ask a clarifying question when the
  request is ambiguous ("two 2 PM meetings — which one?").
* If no LLM is reachable, the graph short-circuits to a deterministic fallback
  parser so the app still works fully offline.

This graph is what both the text chat and the voice widget call — voice is just
STT before and TTS after; the agent never knows the input mode.
"""
from __future__ import annotations

import json
import operator
import re
from datetime import date
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from . import fallback, storage, tools
from .humanize import humanize_date, humanize_range
from .llm import get_llm
from .rag import hybrid_retrieve
from .schemas import EventOut

MAX_TOOL_STEPS = 4


class AgentState(TypedDict, total=False):
    user_id: str
    message: str
    history: list[dict]
    intent: str
    resolved_date: str | None
    retrieved: list[EventOut]
    retrieved_text: str
    tool_calls: Annotated[list[dict], operator.add]  # accumulates across decide loops
    tool_result: dict | None
    tool_name: str | None
    reply: str
    events_out: list[EventOut]
    steps: int
    done: bool
    fallback_result: dict | None
    _db: Session


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def route_intent(state: AgentState) -> dict:
    if not get_llm().connected:
        # no LLM -> deterministic whole-turn fallback
        return {"fallback_result": _run_fallback(state)}
    intent = _llm_classify(state["message"], state["history"])
    return {"intent": intent}


def _run_fallback(state: AgentState) -> dict:
    db = state["_db"]
    return fallback.run_fallback(db, state["user_id"], state["message"])


def resolve_dates(state: AgentState) -> dict:
    return {"resolved_date": fallback._extract_date(state["message"])}


def retrieve(state: AgentState) -> dict:
    db = state["_db"]
    user_id = state["user_id"]
    intent = state.get("intent", "query_schedule")
    day = state.get("resolved_date")
    message = state["message"]

    events: list[EventOut] = []
    if intent in ("query_schedule", "free_check"):
        if day:
            events = storage.events_by_day(db, user_id, day)
            if not events:  # nothing exact on that day; try semantic anyway
                events = hybrid_retrieve(db, user_id, date_from=day, date_to=day, query=message)
        else:
            events = hybrid_retrieve(db, user_id, query=message)
    elif intent in ("update", "delete"):
        events = tools.find_candidate_events(db, user_id, message, day)
    # 'add' / 'chat' need no retrieval up front

    text = _events_to_context(events) or "(no events retrieved)"
    return {"retrieved": events, "retrieved_text": text}


def decide(state: AgentState) -> dict:
    llm = get_llm()
    system = llm.system_prompt()
    prev = state.get("tool_result")
    if prev is not None:
        decision = _llm_decision_after_tool(state, system)
    else:
        decision = _llm_decision_initial(state, system)

    action = decision.get("action")
    if action == "tool_call":
        tool = decision.get("tool")
        args = decision.get("args") or {}
        if tool not in ("get_schedule", "update_schedule"):
            tool = "get_schedule"  # safe default
        steps = state.get("steps", 0) + 1
        return {"tool_calls": [{"name": tool, "args": args}], "steps": steps, "done": False}

    if action == "clarify":
        return {"reply": decision.get("text") or "Could you clarify which event you mean?", "done": True}

    # answer (or unparseable output -> treat as answer)
    return {"reply": decision.get("text") or _fallback_text(state), "done": True}


def execute_tool(state: AgentState) -> dict:
    db = state["_db"]
    call = state["tool_calls"][-1]
    try:
        if call["name"] == "get_schedule":
            result = tools.execute_get_schedule(db, state["user_id"], call.get("args"))
        else:
            result = tools.execute_update_schedule(db, state["user_id"], call.get("args"))
    except Exception as exc:  # never let a bad tool call 500 the request
        result = {"ok": False, "message": f"Something went wrong running that tool: {exc}", "events": []}
    return {"tool_result": result, "tool_name": call["name"]}


def finalize(state: AgentState) -> dict:
    events_out = list(state.get("retrieved", []))
    tr = state.get("tool_result")
    if isinstance(tr, dict):
        for e in tr.get("events", []):
            if e.get("id") not in {x.id for x in events_out}:
                try:
                    events_out.append(EventOut(**e))
                except Exception:
                    continue
    return {"events_out": events_out}


def should_continue(state: AgentState) -> str:
    if state.get("done"):
        return "finalize"
    if state.get("steps", 0) >= MAX_TOOL_STEPS:
        # force an answer rather than looping forever
        return "force_answer"
    return "decide"


def force_answer(state: AgentState) -> dict:
    tr = state.get("tool_result")
    if isinstance(tr, dict):
        msg = tr.get("message")
        if msg:
            return {"reply": msg, "done": True}
    return {"reply": "I did that, but couldn't summarize the result. Ask me again for details.", "done": True}


def build_graph() -> object:
    g = StateGraph(AgentState)
    g.add_node("route_intent", route_intent)
    g.add_node("resolve_dates", resolve_dates)
    g.add_node("retrieve", retrieve)
    g.add_node("decide", decide)
    g.add_node("execute_tool", execute_tool)
    g.add_node("finalize", finalize)
    g.add_node("force_answer", force_answer)

    g.add_edge(START, "route_intent")
    g.add_conditional_edges(
        "route_intent",
        _after_route,
        {"fallback": "finalize", "agentic": "resolve_dates"},
    )
    g.add_edge("resolve_dates", "retrieve")
    g.add_edge("retrieve", "decide")
    g.add_conditional_edges(
        "decide",
        should_continue,
        {"decide": "execute_tool", "finalize": "finalize", "force_answer": "force_answer"},
    )
    g.add_edge("execute_tool", "decide")
    g.add_edge("finalize", END)
    g.add_edge("force_answer", END)
    return g.compile()


def _after_route(state: AgentState) -> str:
    if state.get("fallback_result") is not None:
        return "fallback"
    return "agentic"


# --------------------------------------------------------------------------- #
# LLM helpers
# --------------------------------------------------------------------------- #
def _llm_classify(message: str, history: list[dict]) -> str:
    llm = get_llm()
    msgs = [{"role": "system", "content": (
        "You classify schedule requests. Respond with ONLY a JSON object: "
        '{"intent": "query_schedule" | "add" | "update" | "delete" | "free_check" | "chat"}. '
        f"Today is {date.today().isoformat()}."
    )}]
    for h in history[-6:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": f"Classify this message: {message}"})
    text = llm.complete(msgs)
    if text:
        obj = _parse_json(text)
        intent = obj.get("intent") if isinstance(obj, dict) else None
        if intent in ("query_schedule", "add", "update", "delete", "free_check", "chat"):
            return intent
    return fallback.classify_intent(message)


def _llm_decision_initial(state: AgentState, system: str) -> dict:
    llm = get_llm()
    hist = "\n".join(f"{h['role']}: {h['content']}" for h in state.get("history", [])[-6:]) or "(none)"
    prompt = f"""You are the decision node of a schedule agent.
Context retrieved from the user's schedule:
{state.get("retrieved_text", "")}

Conversation history:
{hist}

User request: "{state['message']}"

Respond with ONLY one JSON object, no prose:
1. Tool call (add event):    {{"action":"tool_call","tool":"update_schedule","args":{{"action":"add","event_data":{{"title":"...","event_date":"YYYY-MM-DD","start_time":"HH:MM","end_time":"HH:MM","category":"meeting|workshop|task|appointment","location":"...","notes":"..."}}}}}}
2. Tool call (update event): {{"action":"tool_call","tool":"update_schedule","args":{{"action":"update","event_id":"...","event_data":{{"title":"...","start_time":"HH:MM","end_time":"HH:MM","location":"..."}}}}}}
3. Tool call (delete event): {{"action":"tool_call","tool":"update_schedule","args":{{"action":"delete","event_id":"..."}}}}
4. Query events:             {{"action":"tool_call","tool":"get_schedule","args":{{"date_from":"YYYY-MM-DD","date_to":"YYYY-MM-DD","query":"..."}}}}
5. Final answer:             {{"action":"answer","text":"short reply, 1-3 sentences"}}
6. Ask for clarification:    {{"action":"clarify","text":"specific question to the user"}}

CRITICAL RULES FOR CREATE/ADD:
- If user says "add/create/schedule" but is missing title, date, start_time, end_time, location, or category → ASK using "clarify"
- Gather: title, date, start time, end time, category (ask what type), location (optional but ask)
- Only call update_schedule with "add" when you have ALL of: title, event_date, start_time, end_time, category
- Do NOT guess or assume defaults. ASK for each missing piece.

CRITICAL RULES FOR MODIFY/UPDATE:
- If user wants to modify but there are multiple events → use get_schedule to retrieve them, then clarify which one
- Ask what field they want to modify (title, start_time, end_time, location, category)
- Ask for the new value for that field
- Only call update_schedule with "update" when you have event_id and the specific field to change

CRITICAL RULES FOR DELETE:
- If user wants to delete, identify the event from retrieved context
- If ambiguous (multiple events), ASK which one
- ALWAYS ask confirmation: "Do you really want to delete [event name] on [date]? This cannot be undone."
- Wait for "yes" or confirmation before calling the delete tool
- Do NOT delete without explicit confirmation

Resolution:
- Resolve relative dates ('tomorrow','Friday','next week') to concrete YYYY-MM-DD in tool args.
- If user hasn't provided enough info, prioritize ASKING over guessing."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    text = llm.complete(msgs)
    if not text:
        return _no_llm_decision(state)
    obj = _parse_json(text)
    if isinstance(obj, dict):
        return obj
    # not JSON -> treat as a direct answer
    return {"action": "answer", "text": text.strip()[:600]}


def _llm_decision_after_tool(state: AgentState, system: str) -> dict:
    llm = get_llm()
    tr = state.get("tool_result") or {}
    tool_name = state.get("tool_name", "unknown")
    
    prompt = f"""Tool "{tool_name}" returned:
{json.dumps(tr, default=str)[:1500]}

Original request: "{state['message']}"

Context from conversation history:
{json.dumps(state.get("history", [])[-3:], default=str)[:500]}

Based on the tool result and the original request:
- If the user asked to add an event and is missing info (title, time, location), clarify what's needed
- If the user asked to modify/delete and the tool succeeded, summarize what happened
- If the tool found multiple events and user needs to pick one, ask "Which one?"
- If waiting for delete confirmation, ask "Do you really want to delete [name]?"

Respond with ONLY one JSON object:
1. Another tool call: {{"action":"tool_call","tool":"...","args":{{...}}}}
2. Final answer:      {{"action":"answer","text":"what happened, 1-3 sentences"}}
3. Clarify:           {{"action":"clarify","text":"question for user"}}"""
    
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    text = llm.complete(msgs)
    if not text:
        return _no_llm_decision(state)
    obj = _parse_json(text)
    if isinstance(obj, dict) and obj.get("action") in ("tool_call", "answer", "clarify"):
        return obj
    return {"action": "answer", "text": text.strip()[:600]}


def _no_llm_decision(state: AgentState) -> dict:
    """If the LLM exists but produced nothing, degrade gracefully."""
    return {"action": "answer", "text": _fallback_text(state)}


def _fallback_text(state: AgentState) -> str:
    tr = state.get("tool_result")
    if isinstance(tr, dict):
        return tr.get("message") or "Done."
    events = state.get("retrieved")
    if events:
        return "Here's what I found: " + "; ".join(
            f"{e.title} {humanize_date(e.event_date)} {humanize_range(e.start_time, e.end_time)}" for e in events[:4]
        )
    return "I couldn't resolve that. Try asking with a specific date or event name."


def _parse_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        obj = json.loads(t[start:end + 1])
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _events_to_context(events: list[EventOut]) -> str:
    lines = []
    for e in events:
        loc = f" @ {e.location}" if e.location else ""
        notes = f" — {e.notes}" if e.notes else ""
        lines.append(
            f"- {e.title} | {e.category} | {humanize_date(e.event_date)} "
            f"{humanize_range(e.start_time, e.end_time)}{loc}{notes}"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
_app = None


def get_graph():
    global _app
    if _app is None:
        _app = build_graph()
    return _app


def run_agent(db: Session, user_id: str, message: str, history: list[dict] | None = None) -> dict:
    """Returns an AgentResponse-shaped dict."""
    initial: AgentState = {
        "user_id": user_id,
        "message": message,
        "history": history or [],
        "intent": "chat",
        "resolved_date": None,
        "retrieved": [],
        "retrieved_text": "",
        "tool_calls": [],
        "tool_result": None,
        "tool_name": None,
        "reply": "",
        "events_out": [],
        "steps": 0,
        "done": False,
        "fallback_result": None,
        "_db": db,
    }
    result = get_graph().invoke(initial)

    fb = result.get("fallback_result")
    if fb is not None:
        return fb

    reply = result.get("reply") or ""
    # Strip out any technical IDs from the reply (UUIDs, database IDs, etc.)
    reply = _clean_reply(reply)
    intent = result.get("intent", "chat")
    tool_calls = [{"name": c["name"], "args": c.get("args", {})} for c in result.get("tool_calls", [])]
    events = [_e_dict(e) for e in result.get("events_out", [])]
    return {
        "reply": reply,
        "intent": intent,
        "tool_calls": tool_calls,
        "events": events,
    }


def _clean_reply(text: str) -> str:
    """Remove technical IDs and internal identifiers from the reply."""
    if not text:
        return text
    
    # Remove UUIDs (e.g., e0567c59-41d8-4870-888d-06cde5b93cc0)
    text = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '', text, flags=re.IGNORECASE)
    
    # Remove "with the id <id>" patterns
    text = re.sub(r'\s*with\s+the\s+id\s+[\w\-]*\.?\s*', '', text, flags=re.IGNORECASE)
    
    # Remove "ID: <value>" or "id <value>" patterns
    text = re.sub(r'\s*[Ii][Dd][\s:]+[\w\-]*\.?\s*', '', text)
    
    # Clean up any excessive whitespace created by removals
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def _e_dict(e: EventOut) -> dict:
    d = e.model_dump()
    d.pop("similarity", None)
    return d
