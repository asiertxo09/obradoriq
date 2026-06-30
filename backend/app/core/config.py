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

    # When true (default in tests/CI), the LLM layer returns deterministic stub
    # text instead of calling the network. Never call a real model in tests.
    llm_offline: bool = True
    # Seed the demo chain on startup (set true on the Render deploy).
    seed_on_start: bool = False
    # Force a wipe + re-seed on startup (e.g. to backfill weather/holiday columns once).
    reseed_on_start: bool = False

    # LLM provider: "anthropic" | "groq" | "nvidia" | "openai_compatible".
    # Groq and NVIDIA are free, OpenAI-compatible endpoints.
    llm_provider: str = "anthropic"
    llm_api_key: str = ""          # generic key; falls back to anthropic_api_key
    anthropic_api_key: str = ""    # kept for backward compatibility
    llm_base_url: str = ""         # override the provider's default endpoint

    # Model routing (Sonnet/Opus rule — see AGENT_FRAMEWORK.md §6a). Leave blank to
    # use the selected provider's default reasoning/execution models.
    model_reasoning: str = ""      # reasoning tier (judgment) — e.g. Opus / llama-70b
    model_execution: str = ""      # execution tier (well-defined) — e.g. Sonnet / llama-8b

    def api_key(self) -> str:
        return self.llm_api_key or self.anthropic_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
