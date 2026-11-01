from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "workforce-planning-engine"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8020
    log_level: str = "INFO"
    tz: str = "America/Sao_Paulo"

    optimizer_default_shift_minutes: int = Field(default=480, ge=1)
    optimizer_max_assignments_per_collaborator_per_day: int = Field(default=1, ge=1)
    optimizer_default_overtime_weight: int = Field(default=100, ge=1)
    optimizer_default_fairness_weight: int = Field(default=5, ge=0)
    optimizer_default_continuity_weight: int = Field(default=3, ge=0)
    optimizer_default_affinity_weight: int = Field(default=10, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
