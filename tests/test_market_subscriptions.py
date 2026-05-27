from __future__ import annotations

import unittest
from collections.abc import Callable
from typing import Any

from qmtserver.errors import QmtInvalidSubscriptionRequestError
from qmtserver.market.subscription_service import MarketSubscriptionService


class RecordingAdapter:
    def __init__(self) -> None:
        self.subscribe_calls: list[dict[str, Any]] = []
        self.unsubscribe_calls: list[Any] = []

    def subscribe(
        self,
        *,
        symbols: list[str],
        period: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> int:
        self.subscribe_calls.append({"symbols": symbols, "period": period, "callback": callback})
        return 7

    def unsubscribe(self, upstream_id: Any) -> None:
        self.unsubscribe_calls.append(upstream_id)


class RecordingBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def publish_threadsafe(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.events.append((event_type, data or {}, meta or {}))


class InitialQuoteAdapter(RecordingAdapter):
    def subscribe(
        self,
        *,
        symbols: list[str],
        period: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> int:
        upstream_id = super().subscribe(symbols=symbols, period=period, callback=callback)
        callback({"schema": "market.quote.v1", "symbol": symbols[0], "last_price": 10.25})
        return upstream_id


class MarketSubscriptionServiceTests(unittest.TestCase):
    def test_create_subscription_stores_state_and_publishes_lifecycle_event(self) -> None:
        adapter = RecordingAdapter()
        bus = RecordingBus()
        service = MarketSubscriptionService(
            adapter=adapter,
            event_bus=bus,
            id_factory=lambda: "sub_test",
        )

        subscription = service.create(symbols=["000001.SZ"], period="tick")

        self.assertEqual(subscription.subscription_id, "sub_test")
        self.assertEqual(subscription.status, "active")
        self.assertEqual(subscription.upstream_id, 7)
        self.assertEqual(adapter.subscribe_calls[0]["symbols"], ["000001.SZ"])
        self.assertEqual(adapter.subscribe_calls[0]["period"], "tick")
        self.assertEqual(service.get("sub_test"), subscription)
        self.assertEqual(bus.events[0][0], "market_subscription")
        self.assertEqual(bus.events[0][1]["schema"], "market.subscription.v1")
        self.assertEqual(bus.events[0][1]["status"], "active")

    def test_create_subscription_rejects_empty_symbols_before_upstream_call(self) -> None:
        adapter = RecordingAdapter()
        service = MarketSubscriptionService(
            adapter=adapter,
            event_bus=RecordingBus(),
            id_factory=lambda: "sub_test",
        )

        with self.assertRaises(QmtInvalidSubscriptionRequestError):
            service.create(symbols=[], period="tick")

        self.assertEqual(adapter.subscribe_calls, [])

    def test_stop_subscription_marks_stopped_and_calls_upstream_unsubscribe(self) -> None:
        adapter = RecordingAdapter()
        bus = RecordingBus()
        service = MarketSubscriptionService(
            adapter=adapter,
            event_bus=bus,
            id_factory=lambda: "sub_test",
        )
        service.create(symbols=["000001.SZ"], period="tick")

        stopped = service.stop("sub_test")

        self.assertEqual(stopped.status, "stopped")
        self.assertEqual(adapter.unsubscribe_calls, [7])
        self.assertEqual(bus.events[-1][0], "market_subscription")
        self.assertEqual(bus.events[-1][1]["status"], "stopped")

    def test_initial_quote_during_create_is_published(self) -> None:
        bus = RecordingBus()
        service = MarketSubscriptionService(
            adapter=InitialQuoteAdapter(),
            event_bus=bus,
            id_factory=lambda: "sub_test",
        )

        service.create(symbols=["000001.SZ"], period="tick")

        quote_events = [event for event in bus.events if event[0] == "market_quote"]
        self.assertEqual(len(quote_events), 1)
        self.assertEqual(quote_events[0][1]["schema"], "market.quote.v1")
        self.assertEqual(quote_events[0][2]["subscription_id"], "sub_test")


if __name__ == "__main__":
    unittest.main()
