from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

SUBSCRIPTION_SCHEMA = "market.subscription.v1"
QUOTE_SCHEMA = "market.quote.v1"
SUPPORTED_SUBSCRIPTION_PERIODS = ("tick",)

SubscriptionStatus = Literal["starting", "active", "degraded", "stopped", "error"]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class MarketSubscriptionRequest:
    symbols: list[str]
    period: str = "tick"


@dataclass(frozen=True)
class MarketSubscription:
    subscription_id: str
    symbols: list[str]
    period: str
    status: SubscriptionStatus
    created_at: str
    updated_at: str
    upstream_id: Any = None
    last_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SUBSCRIPTION_SCHEMA,
            "subscription_id": self.subscription_id,
            "symbols": self.symbols,
            "period": self.period,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "upstream_id": self.upstream_id,
            "last_error": self.last_error,
        }
