from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Protocol

from qmtserver.errors import (
    QmtInvalidSubscriptionRequestError,
    QmtMarketSubscriptionNotFoundError,
)
from qmtserver.market.subscription_models import (
    SUPPORTED_SUBSCRIPTION_PERIODS,
    MarketSubscription,
    SubscriptionStatus,
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
        now_factory: Callable[[], datetime] | None = None,
        callback_stale_after_seconds: int = 30,
    ) -> None:
        self.adapter = adapter
        self.event_bus = event_bus
        self.id_factory = id_factory or _subscription_id
        self.now_factory = now_factory or _utc_now
        self.callback_stale_after_seconds = callback_stale_after_seconds
        self._subscriptions: dict[str, MarketSubscription] = {}
        self._latest_quotes: dict[str, dict[str, Any]] = {}
        self._diagnostics: dict[str, dict[str, Any]] = {}
        self._event_seq = 0

    def create(self, *, symbols: list[str], period: str = "tick") -> MarketSubscription:
        clean_symbols = self._validate(symbols, period)
        subscription_id = self.id_factory()
        now = self._now_iso()
        subscription = MarketSubscription(
            subscription_id=subscription_id,
            symbols=clean_symbols,
            period=period,
            status="starting",
            created_at=now,
            updated_at=now,
        )
        self._subscriptions[subscription_id] = subscription
        self._diagnostics[subscription_id] = _empty_diagnostics(subscription)
        try:
            upstream_id = self.adapter.subscribe(
                symbols=clean_symbols,
                period=period,
                callback=lambda payload: self.handle_quote(subscription_id, payload),
            )
        except Exception as exc:
            degraded = self._set_status(
                subscription_id,
                "degraded",
                last_error=f"{type(exc).__name__}: {exc}",
            )
            self._publish_subscription(degraded)
            return degraded
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

    def diagnostics(self, subscription_id: str) -> dict[str, Any]:
        subscription = self.get(subscription_id)
        diagnostics = dict(self._diagnostics.get(subscription_id, _empty_diagnostics(subscription)))
        now = self.now_factory()
        diagnostics.update(
            {
                "subscription_id": subscription.subscription_id,
                "symbols": subscription.symbols,
                "period": subscription.period,
                "status": subscription.status,
                "active_symbols": subscription.symbols if subscription.status == "active" else [],
                "last_error": subscription.last_error,
                "degraded_reason": subscription.last_error
                if subscription.status == "degraded"
                else None,
                "seconds_since_last_quote": _seconds_since(diagnostics["last_quote_at"], now),
                "seconds_since_last_callback": _seconds_since(
                    diagnostics["last_callback_at"],
                    now,
                ),
                "is_callback_active": _callback_active(
                    diagnostics["last_callback_at"],
                    now,
                    self.callback_stale_after_seconds,
                ),
                "callback_stale_after_seconds": self.callback_stale_after_seconds,
            }
        )
        return diagnostics

    def latest_quotes(self, symbols: list[str] | None = None) -> dict[str, Any]:
        requested = [item.strip() for item in symbols or [] if item.strip()]
        quote_symbols = requested or sorted(self._latest_quotes)

        quotes: list[dict[str, Any]] = []
        missing_symbols: list[str] = []
        for symbol in quote_symbols:
            cached = self._latest_quotes.get(symbol)
            if cached is None:
                missing_symbols.append(symbol)
                continue
            quotes.append(dict(cached))
        return {
            "schema": "market.latest_quotes.v1",
            "quotes": quotes,
            "missing_symbols": missing_symbols,
        }

    def stop(self, subscription_id: str) -> MarketSubscription:
        subscription = self.get(subscription_id)
        if subscription.status != "stopped":
            self.adapter.unsubscribe(subscription.upstream_id)
        stopped = self._set_status(subscription_id, "stopped")
        self._publish_subscription(stopped)
        return stopped

    def recover(self, subscription_id: str) -> MarketSubscription:
        subscription = self.get(subscription_id)
        if subscription.status == "active":
            self.adapter.unsubscribe(subscription.upstream_id)
        try:
            upstream_id = self.adapter.subscribe(
                symbols=subscription.symbols,
                period=subscription.period,
                callback=lambda payload: self.handle_quote(subscription_id, payload),
            )
        except Exception as exc:
            degraded = self._set_status(
                subscription_id,
                "degraded",
                last_error=f"{type(exc).__name__}: {exc}",
            )
            self._diagnostics[subscription_id] = _empty_diagnostics(degraded)
            self._publish_subscription(degraded)
            return degraded
        recovered = self._set_status(
            subscription_id,
            "active",
            upstream_id=upstream_id,
            last_error=None,
        )
        self._diagnostics[subscription_id] = _empty_diagnostics(recovered)
        self._publish_subscription(recovered)
        self.event_bus.publish_threadsafe(
            "market_subscription_recovered",
            recovered.as_dict(),
            {"subscription_id": subscription_id, "source": "qmtserver"},
        )
        return recovered

    def handle_quote(self, subscription_id: str, payload: dict[str, Any]) -> None:
        subscription = self.get(subscription_id)
        if subscription.status not in {"starting", "active"}:
            return
        quote = dict(payload)
        quote_source = quote.pop("__qmt_quote_source", "callback")
        event_seq = self._next_event_seq()
        self._record_quote(
            subscription=subscription,
            quote=quote,
            quote_source=quote_source,
            event_seq=event_seq,
        )
        self.event_bus.publish_threadsafe(
            "market_quote",
            quote,
            {
                "subscription_id": subscription_id,
                "source": "xtdata",
                "quote_source": quote_source,
                "event_seq": event_seq,
            },
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
            updated_at=self._now_iso(),
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

    def _record_quote(
        self,
        *,
        subscription: MarketSubscription,
        quote: dict[str, Any],
        quote_source: str,
        event_seq: int,
    ) -> None:
        symbol = str(quote.get("symbol", "")).strip()
        now = self._now_iso()
        if symbol:
            self._latest_quotes[symbol] = {
                "symbol": symbol,
                "quote": dict(quote),
                "quote_source": quote_source,
                "updated_at": now,
                "subscription_id": subscription.subscription_id,
                "event_seq": event_seq,
            }

        current = dict(
            self._diagnostics.get(subscription.subscription_id, _empty_diagnostics(subscription))
        )
        current["last_quote_at"] = now
        current["last_quote_source"] = quote_source
        current["last_event_seq"] = event_seq
        if quote_source == "initial":
            current["initial_quote_count"] = int(current["initial_quote_count"]) + 1
            current["last_initial_quote_at"] = now
        else:
            current["callback_count"] = int(current["callback_count"]) + 1
            current["last_callback_at"] = now
        self._diagnostics[subscription.subscription_id] = current

    def _next_event_seq(self) -> int:
        self._event_seq += 1
        return self._event_seq

    def _now_iso(self) -> str:
        return self.now_factory().isoformat()

    def _validate(self, symbols: list[str], period: str) -> list[str]:
        clean_symbols = [item.strip() for item in symbols if item.strip()]
        if not clean_symbols:
            raise QmtInvalidSubscriptionRequestError("symbols must include at least one symbol")
        if period not in SUPPORTED_SUBSCRIPTION_PERIODS:
            raise QmtInvalidSubscriptionRequestError(f"unsupported period: {period}")
        return clean_symbols


def _subscription_id() -> str:
    return f"sub_{uuid.uuid4().hex}"


def _empty_diagnostics(subscription: MarketSubscription) -> dict[str, Any]:
    return {
        "schema": "market.subscription_diagnostics.v1",
        "subscription_id": subscription.subscription_id,
        "symbols": subscription.symbols,
        "period": subscription.period,
        "status": subscription.status,
        "active_symbols": subscription.symbols if subscription.status == "active" else [],
        "callback_count": 0,
        "initial_quote_count": 0,
        "last_quote_at": None,
        "last_initial_quote_at": None,
        "last_callback_at": None,
        "last_quote_source": None,
        "last_event_seq": None,
        "seconds_since_last_quote": None,
        "seconds_since_last_callback": None,
        "is_callback_active": False,
        "callback_stale_after_seconds": 30,
        "last_error": subscription.last_error,
        "degraded_reason": subscription.last_error if subscription.status == "degraded" else None,
    }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _seconds_since(value: Any, now: datetime) -> float | None:
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return max(0.0, (now - timestamp).total_seconds())


def _callback_active(value: Any, now: datetime, stale_after_seconds: int) -> bool:
    seconds = _seconds_since(value, now)
    return seconds is not None and seconds <= stale_after_seconds
