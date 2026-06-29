"""Application settings, loaded from environment."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default to a local SQLite file so tests and `uvicorn` run with zero setup;
    # Render/compose inject a real Postgres DATABASE_URL.
    database_url: str = "sqlite:///./obradoriq.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30

    anthropic_api_key: str = ""
    # When true (default in tests/CI), the LLM layer returns deterministic stub
    # text instead of calling the network. Never call a real model in tests.
    llm_offline: bool = True
    # Seed the demo chain on startup (set true on the Render deploy).
    seed_on_start: bool = False

    # Model routing (Sonnet/Opus rule — see AGENT_FRAMEWORK.md §6a).
    model_reasoning: str = "claude-opus-4-8"
    model_execution: str = "claude-sonnet-4-6"


@lru_cache
def get_settings() -> Settings:
    return Settings()
