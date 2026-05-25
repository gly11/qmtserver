from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QMT_",
        extra="ignore",
    )

    userdata: Path | None = None
    account_id: str | None = None
    account_type: str = "STOCK"
    host: str = "127.0.0.1"
    port: int = 8000
    quote_code: str = "000001.SZ"
    enable_trading: bool = False
    api_token: str | None = None
    auto_connect: bool = True
    trader_timeout_ms: int = Field(default=5000, ge=1)


def load_settings(**overrides: Any) -> Settings:
    values = {key: value for key, value in overrides.items() if value is not None}
    return Settings(**values)
