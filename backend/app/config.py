"""Application settings — read from environment / backend/.env.

Everything here is free-tier friendly: the only things you MAY need are a local
Ollama install (fully free) or a free API key (Groq / Gemini). Embeddings are
local ONNX and never touch the network.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    PORT: int = 8005
    HOST: str = "127.0.0.1"
    FRONTEND_DIST: str = str(BACKEND_DIR.parent / "frontend" / "dist")

    # --- Storage ---
    DATABASE_PATH: str = str(BACKEND_DIR / "data" / "schedule.db")
    CHROMA_PATH: str = str(BACKEND_DIR / "data" / "chroma")

    # --- Sessions ---
    SESSION_TTL_DAYS: int = 30

    # --- Seed ---
    SEED_ON_START: bool = False

    # --- Google OAuth (required for multi-user) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # --- Google Calendar sync (enabled when Google OAuth is configured) ---
    GOOGLE_CALENDAR_ENABLED: bool = True
    GOOGLE_TOKEN_KEY: str = ""

    # --- LLM provider ---
    # auto = pick the first available: ollama (local) -> groq -> gemini -> openai_compatible -> anthropic
    LLM_PROVIDER: str = "auto"
    LLM_TIMEOUT: float = 40.0

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    OPENAI_BASE_URL: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-latest"
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"

    # --- OmniRoute (Anthropic-compatible local proxy) ---
    OMNIROUTE_BASE_URL: str = "http://localhost:20128"
    OMNIROUTE_AUTH_TOKEN: str = "omniroute"
    OMNIROUTE_MODEL: str = "auto/best-free"

    # --- Reminders / digest ---
    REMINDER_LEAD_MIN: int = 10
    DIGEST_TIME: str = "07:00"
    REMINDER_POLL_SECONDS: int = 45

    # --- Vector search ---
    SEMANTIC_TOP_K: int = 5
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- Sarvam AI (speech-to-text + text-to-speech) ---
    # Get a key from https://dashboard.sarvam.ai — leave blank to disable voice.
    SARVAM_API_KEY: str = ""
    SARVAM_BASE_URL: str = "https://api.sarvam.ai"
    SARVAM_STT_MODEL: str = "saarika:v2.5"
    SARVAM_STT_LANGUAGE: str = "unknown"  # "unknown" = auto-detect; or e.g. "en-IN", "hi-IN"
    SARVAM_TTS_MODEL: str = "bulbul:v2"
    SARVAM_TTS_LANGUAGE: str = "en-IN"
    SARVAM_TTS_SPEAKER: str = "anushka"
    SARVAM_TIMEOUT: float = 30.0

    @property
    def voice_enabled(self) -> bool:
        return bool(self.SARVAM_API_KEY)

    def data_dir(self) -> Path:
        p = Path(self.DATABASE_PATH).parent
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure_dirs(self) -> None:
        self.data_dir()
        Path(self.CHROMA_PATH).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
