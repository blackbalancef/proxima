from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(min_length=1)
    allowed_user_ids: list[int]
    database_url: str = Field(min_length=1)
    work_dir: Path = Field(default_factory=lambda: Path.cwd() / "projects")
    openai_api_key: str | None = None
    whisper_language: str | None = None
    anthropic_api_key: str | None = None
    log_level: Literal["debug", "info", "warn", "error"] = "info"

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, value: object) -> list[int]:
        if isinstance(value, list):
            ids = [int(v) for v in value]
            if any(user_id <= 0 for user_id in ids):
                raise ValueError("allowed_user_ids must contain positive integers")
            return ids
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("allowed_user_ids must contain positive integers")
            return [value]
        if isinstance(value, str):
            items = [part.strip() for part in value.split(",") if part.strip()]
            ids = [int(item) for item in items]
            if any(user_id <= 0 for user_id in ids):
                raise ValueError("allowed_user_ids must be positive integers")
            return ids
        raise ValueError("allowed_user_ids must be an integer or comma-separated integers")

    @field_validator("work_dir", mode="before")
    @classmethod
    def normalize_work_dir(cls, value: object) -> Path:
        if isinstance(value, Path):
            path = value.resolve()
        elif isinstance(value, str) and value.strip():
            path = Path(value).expanduser().resolve()
        else:
            path = (Path.cwd() / "projects").resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
