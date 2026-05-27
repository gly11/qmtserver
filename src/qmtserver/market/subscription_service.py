from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from typing import Any, Protocol

from qmtserver.errors import (
    QmtInvalidSubscriptionRequestError,
    QmtMarketSubscriptionNotFoundError,
)
from qmtserver.market.subscription_models import (
    SUPPORTED_SUBSCRIPTION_PERIODS,
    MarketSubscription,
    SubscriptionStatus,
    utc_now_iso,
)


class MarketSubscriptionAdapter(Protocol):
    def subscribe(
        self,
        *,
        symbols: list[str],
        period: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> Any: ...

    def unsubscribe(self, upstream_id: Any) -> None: ...


class EventPublisher(Protocol):
    def publish_threadsafe(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None: ...


class MarketSubscriptionService:
    def __init__(
        self,
        *,
        adapter: MarketSubscriptionAdapter,
        event_bus: EventPublisher,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.adapter = adapter
        self.event_bus = event_bus
        self.id_factory = id_factory or _subscription_id
        self._subscriptions: dict[str, MarketSubscription] = {}

    def create(self, *, symbols: list[str], period: str = "tick") -> MarketSubscription:
        clean_symbols = self._validate(symbols, period)
        subscription_id = self.id_factory()
        now = utc_now_iso()
        subscription = MarketSubscription(
            subscription_id=subscription_id,
            symbols=clean_symbols,
            period=period,
            status="starting",
            created_at=now,
            updated_at=now,
        )
        self._subscriptions[subscription_id] = subscription
        upstream_id = self.adapter.subscribe(
            symbols=clean_symbols,
            period=period,
            callback=lambda payload: self.handle_quote(subscription_id, payload),
        )
        subscription = self._set_status(
            subscription_id,
            "active",
            upstream_id=upstream_id,
        )
        self._publish_subscription(subscription)
        return subscription

    def list_subscriptions(self) -> list[MarketSubscription]:
        return list(self._subscriptions.values())

    def get(self, subscription_id: str) -> MarketSubscription:
        try:
            return self._subscriptions[subscription_id]
        except KeyError as exc:
            raise QmtMarketSubscriptionNotFoundError(subscription_id) from exc

    def stop(self, subscription_id: str) -> MarketSubscription:
        subscription = self.get(subscription_id)
        if subscription.status != "stopped":
            self.adapter.unsubscribe(subscription.upstream_id)
        stopped = self._set_status(subscription_id, "stopped")
        self._publish_subscription(stopped)
        return stopped

    def handle_quote(self, subscription_id: str, payload: dict[str, Any]) -> None:
        subscription = self.get(subscription_id)
        if subscription.status not in {"starting", "active"}:
            return
        self.event_bus.publish_threadsafe(
            "market_quote",
            payload,
            {"subscription_id": subscription_id, "source": "xtdata"},
        )

    def _set_status(
        self,
        subscription_id: str,
        status: SubscriptionStatus,
        *,
        upstream_id: Any = None,
        last_error: str | None = None,
    ) -> MarketSubscription:
        current = self.get(subscription_id)
        updated = replace(
            current,
            status=status,
            updated_at=utc_now_iso(),
            upstream_id=current.upstream_id if upstream_id is None else upstream_id,
            last_error=last_error,
        )
        self._subscriptions[subscription_id] = updated
        return updated

    def _publish_subscription(self, subscription: MarketSubscription) -> None:
        self.event_bus.publish_threadsafe(
            "market_subscription",
            subscription.as_dict(),
            {"subscription_id": subscription.subscription_id, "source": "qmtserver"},
        )

    def _validate(self, symbols: list[str], period: str) -> list[str]:
        clean_symbols = [item.strip() for item in symbols if item.strip()]
        if not clean_symbols:
            raise QmtInvalidSubscriptionRequestError("symbols must include at least one symbol")
        if period not in SUPPORTED_SUBSCRIPTION_PERIODS:
            raise QmtInvalidSubscriptionRequestError(f"unsupported period: {period}")
        return clean_symbols


def _subscription_id() -> str:
    return f"sub_{uuid.uuid4().hex}"
