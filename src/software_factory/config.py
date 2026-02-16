"""Runtime configuration for the software factory."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="local")
    database_url: str = Field(
        default="postgresql+psycopg://factory:factory@localhost:5432/factory",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    default_lease_ttl_seconds: int = Field(default=900, alias="DEFAULT_LEASE_TTL_SECONDS")
    run_heartbeat_timeout_seconds: int = Field(default=120, alias="RUN_HEARTBEAT_TIMEOUT_SECONDS")
    max_run_minutes: int = Field(default=45, alias="MAX_RUN_MINUTES")
    max_run_tokens: int = Field(default=120_000, alias="MAX_RUN_TOKENS")

    enabled_harnesses: list[str] = Field(default_factory=lambda: ["codex"], alias="ENABLED_HARNESSES")

    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    linear_api_key: str | None = Field(default=None, alias="LINEAR_API_KEY")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")

    @field_validator("enabled_harnesses", mode="before")
    @classmethod
    def _parse_enabled_harnesses(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
