from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # Envisalink connection defaults (overridable at runtime via Settings UI).
    evl_host: str = "192.168.1.100"
    evl_port: int = 4025
    evl_password: str = ""

    # Secret used to derive the at-rest encryption key and to sign session JWTs.
    app_secret: str = "change-me-insecure-default"

    # SQLite database file path.
    db_path: str = "/data/vista.db"

    # Extra CORS origins (comma separated).
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        evl_host=os.getenv("EVL_HOST", "192.168.1.100"),
        evl_port=int(os.getenv("EVL_PORT", "4025")),
        evl_password=os.getenv("EVL_PASSWORD", ""),
        app_secret=os.getenv("APP_SECRET", "change-me-insecure-default"),
        db_path=os.getenv("DB_PATH", "/data/vista.db"),
        cors_origins=os.getenv("CORS_ORIGINS", ""),
    )
