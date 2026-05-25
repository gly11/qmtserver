from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
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
    trading_dry_run: bool = True
    max_order_volume: int = Field(default=100000, ge=1)
    max_order_amount: float = Field(default=1000000, ge=0)
    allowed_accounts: str | None = None
    ws_heartbeat_seconds: float = Field(default=15, gt=0)
    ws_client_queue_size: int = Field(default=1000, ge=1)
    api_token: str | None = None
    require_token: bool = False
    audit_log: bool = True
    audit_log_args: bool = True
    auto_connect: bool = True
    connect_on_startup: bool = True
    connect_quote: bool = True
    connect_trader: bool = True
    trader_timeout_ms: int = Field(default=5000, ge=1)

    @model_validator(mode="after")
    def validate_token_requirement(self) -> Settings:
        if self.require_token and not self.api_token:
            raise ValueError("QMT_REQUIRE_TOKEN=true requires QMT_API_TOKEN to be set")
        return self

    def trading_allowed_accounts(self) -> set[str]:
        if self.allowed_accounts:
            return {
                account.strip() for account in self.allowed_accounts.split(",") if account.strip()
            }
        if self.account_id:
            return {self.account_id}
        return set()


def load_settings(**overrides: Any) -> Settings:
    values = {key: value for key, value in overrides.items() if value is not None}
    return Settings(**values)
