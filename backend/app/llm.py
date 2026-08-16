"""Pluggable LLM client — every provider is free-tier friendly.

Resolution order for LLM_PROVIDER=auto:
  1. Ollama (local, http://localhost:11434) — genuinely $0, no account, private
  2. Groq free tier (needs GROQ_API_KEY from console.groq.com)
  3. Google Gemini free tier (needs GEMINI_API_KEY)
  4. any OpenAI-compatible endpoint (OPENAI_BASE_URL + OPENAI_API_KEY)
  5. Anthropic (ANTHROPIC_API_KEY)

If none is reachable, `status().connected` is False and the agent uses the
deterministic fallback parser — the app still works, fully offline.
"""
from __future__ import annotations

import json
import time

import httpx

from .config import settings

SYSTEM_PROMPT = (
    "You are a concise, helpful schedule assistant. Today's date is {today_iso} ({today_human}). "
    "Resolve relative dates ('tomorrow', 'Friday', 'next week') against today's date — never guess. "
    "You are given retrieved schedule context and/or tool results to ground every answer. "
    "Never claim an event exists unless it is in the provided context. "
    "Keep answers short (this may be read aloud by a voice interface): 1-3 sentences, no markdown, "
    "no bullet lists unless the user asked for a list. Include exact times and dates when you state facts.\n"
    
    "IMPORTANT: Never include technical IDs (event IDs, database IDs, UUIDs, internal identifiers) in your responses. "
    "Always provide human-friendly responses that a non-technical user would understand. "
    "Focus on what was accomplished, not technical details.\n"
    
    "CONVERSATIONAL SCHEDULING RULES:\n"
    "When the user wants to CREATE a schedule, ask clarifying questions BEFORE calling the tool:\n"
    "  1. What type of schedule? (Meeting, Workshop, Task, Appointment, etc.)\n"
    "  2. What is the event title/name?\n"
    "  3. What date? (resolve relative dates)\n"
    "  4. What is the start time?\n"
    "  5. What is the end time?\n"
    "  6. Where is it located? (optional but ask)\n"
    "Only call update_schedule when you have ALL these details. If any are missing, ask the user.\n\n"
    
    "When the user wants to MODIFY an existing schedule, ask:\n"
    "  1. Which specific event do they want to modify? (if ambiguous, ask them to clarify)\n"
    "  2. What would they like to modify? (title, start time, end time, location, type/category)\n"
    "  3. Ask for the new value for that specific field\n"
    "Confirm changes before executing.\n\n"
    
    "When the user wants to DELETE a schedule, ALWAYS ask for confirmation:\n"
    "  1. Identify which event(s) they want to delete\n"
    "  2. Ask: 'Do you really want to delete [event name] on [date]? This cannot be undone.'\n"
    "Only delete after explicit confirmation.\n\n"
    
    "For clarifications, use the 'clarify' action to ask follow-up questions instead of guessing.\n"
    
    "Formatting rules for any date/time you SAY to the user (tool args still use YYYY-MM-DD / 24-hour HH:MM internally):\n"
    "- Times: always 12-hour clock with AM/PM, e.g. '2:00 PM'. Never say 24-hour time like '14:00'.\n"
    "- Dates: say the day and month only, e.g. '15 August'. Do NOT include the year "
    "unless the date's year is different from the current year ({this_year}) — "
    "only then say the full date, e.g. '15 August 2027'."
)


def _ollama_style_base_url() -> str:
    """Build base URL for OmniRoute / Anthropic-compatible proxies."""
    return settings.OMNIROUTE_BASE_URL.rstrip("/")


class LLMClient:
    def __init__(self) -> None:
        self.provider, self.model, self.connected = self._resolve()

    # ------------------------------------------------------------------ #
    def _resolve(self) -> tuple[str, str, bool]:
        p = settings.LLM_PROVIDER.strip().lower()
        if p == "ollama":
            return ("ollama", settings.OLLAMA_MODEL, self._ping_ollama())
        if p == "groq":
            return ("groq", settings.GROQ_MODEL, bool(settings.GROQ_API_KEY))
        if p == "gemini":
            return ("gemini", settings.GEMINI_MODEL, bool(settings.GEMINI_API_KEY))
        if p == "openai_compatible":
            return ("openai_compatible", settings.OPENAI_MODEL, bool(settings.OPENAI_BASE_URL and settings.OPENAI_API_KEY))
        if p == "anthropic":
            return ("anthropic", settings.ANTHROPIC_MODEL, bool(settings.ANTHROPIC_API_KEY))
        if p == "omniroute":
            return ("omniroute", settings.OMNIROUTE_MODEL, bool(settings.OMNIROUTE_BASE_URL and settings.OMNIROUTE_AUTH_TOKEN))
        if p in ("auto", ""):
            return self._resolve_auto()
        # unknown provider name -> treat as none, app falls back to parser
        return ("none", "", False)

    def _resolve_auto(self) -> tuple[str, str, bool]:
        if self._ping_ollama():
            return ("ollama", settings.OLLAMA_MODEL, True)
        if settings.GROQ_API_KEY:
            return ("groq", settings.GROQ_MODEL, True)
        if settings.GEMINI_API_KEY:
            return ("gemini", settings.GEMINI_MODEL, True)
        if settings.OPENAI_BASE_URL and settings.OPENAI_API_KEY:
            return ("openai_compatible", settings.OPENAI_MODEL, True)
        if settings.ANTHROPIC_API_KEY:
            return ("anthropic", settings.ANTHROPIC_MODEL, True)
        if settings.OMNIROUTE_BASE_URL and settings.OMNIROUTE_AUTH_TOKEN:
            return ("omniroute", settings.OMNIROUTE_MODEL, True)
        return ("none", "", False)

    def _ping_ollama(self) -> bool:
        try:
            r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    def complete(self, messages: list[dict], temperature: float = 0.2) -> str | None:
        """messages: list of {"role": "system"|"user"|"assistant", "content": str}."""
        if not self.connected:
            return None
        t0 = time.monotonic()
        try:
            if self.provider == "ollama":
                return self._ollama(messages, temperature)
            if self.provider == "groq":
                return self._openai_style(messages, temperature)
            if self.provider == "openai_compatible":
                return self._openai_style(messages, temperature)
            if self.provider == "gemini":
                return self._gemini(messages, temperature)
            if self.provider == "anthropic":
                return self._anthropic(messages, temperature)
            if self.provider == "omniroute":
                return self._omniroute(messages, temperature)
        except Exception as exc:
            print(f"[llm] {self.provider} call failed after {time.monotonic() - t0:.2f}s: {exc}")
            return None
        finally:
            print(f"[llm] {self.provider} ({self.model}) call took {time.monotonic() - t0:.2f}s")
        return None

    # ------------------------------------------------------------------ #
    def _ollama(self, messages, temperature) -> str | None:
        body = {"model": self.model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        r = httpx.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=body, timeout=settings.LLM_TIMEOUT)
        r.raise_for_status()
        return r.json().get("message", {}).get("content")

    def _openai_style(self, messages, temperature) -> str | None:
        url = f"{settings.GROQ_BASE_URL}/chat/completions" if self.provider == "groq" else \
              f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
        key = settings.GROQ_API_KEY if self.provider == "groq" else settings.OPENAI_API_KEY
        body = {"model": self.model, "messages": messages, "temperature": temperature}
        r = httpx.post(url, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=settings.LLM_TIMEOUT)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _gemini(self, messages, temperature) -> str | None:
        url = f"{settings.GEMINI_BASE_URL}/models/{self.model}:generateContent"
        contents: list[dict] = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        # collapse consecutive same-role messages (Gemini rejects them)
        merged: list[dict] = []
        for c in contents:
            if merged and merged[-1]["role"] == c["role"]:
                merged[-1]["parts"][0]["text"] += "\n" + c["parts"][0]["text"]
            else:
                merged.append(c)
        r = httpx.post(url, params={"key": settings.GEMINI_API_KEY},
                       json={"contents": merged, "generationConfig": {"temperature": temperature}},
                       timeout=settings.LLM_TIMEOUT)
        r.raise_for_status()
        candidates = r.json().get("candidates") or []
        if not candidates:
            return None
        return candidates[0].get("content", {}).get("parts", [{}])[0].get("text")

    def _anthropic(self, messages, temperature) -> str | None:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
        url = f"{settings.ANTHROPIC_BASE_URL}/v1/messages"
        body = {"model": self.model, "max_tokens": 1024, "temperature": temperature, "messages": turns}
        if system:
            body["system"] = system
        r = httpx.post(url, json=body, headers={
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        }, timeout=settings.LLM_TIMEOUT)
        r.raise_for_status()
        blocks = r.json().get("content") or []
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text") or None

    def _omniroute(self, messages, temperature) -> str | None:
        """OmniRoute is Anthropic-compatible. Uses ANTHROPIC_BASE_URL pattern but with OmniRoute auth."""
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
        url = f"{_ollama_style_base_url()}/v1/messages"
        body = {"model": self.model, "max_tokens": 1024, "temperature": temperature, "messages": turns}
        if system:
            body["system"] = system
        r = httpx.post(url, json=body, headers={
            "x-api-key": settings.OMNIROUTE_AUTH_TOKEN,
            "anthropic-version": "2023-06-01",
        }, timeout=settings.LLM_TIMEOUT)
        r.raise_for_status()
        blocks = r.json().get("content") or []
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text") or None

    # ------------------------------------------------------------------ #
    def system_prompt(self) -> str:
        from datetime import date

        from .humanize import humanize_date

        today = date.today()
        return SYSTEM_PROMPT.format(
            today_iso=today.isoformat(),
            today_human=humanize_date(today.isoformat()),
            this_year=today.year,
        )

    def status(self) -> dict:
        return {"provider": self.provider, "model": self.model, "connected": self.connected}


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def reset_client() -> None:
    global _client
    _client = None
