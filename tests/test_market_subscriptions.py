from __future__ import annotations

import unittest
from collections.abc import Callable
from datetime import UTC, datetime
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
        callback(
            {
                "schema": "market.quote.v1",
                "symbol": symbols[0],
                "last_price": 10.25,
                "__qmt_quote_source": "initial",
            }
        )
        return upstream_id


class FailingSubscribeAdapter(RecordingAdapter):
    def subscribe(
        self,
        *,
        symbols: list[str],
        period: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> int:
        raise RuntimeError("quote disconnected")


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

    def test_quote_source_is_published_in_meta_without_leaking_internal_key(self) -> None:
        bus = RecordingBus()
        service = MarketSubscriptionService(
            adapter=RecordingAdapter(),
            event_bus=bus,
            id_factory=lambda: "sub_test",
        )
        service.create(symbols=["000001.SZ"], period="tick")

        service.handle_quote(
            "sub_test",
            {
                "schema": "market.quote.v1",
                "symbol": "000001.SZ",
                "last_price": 10.25,
                "__qmt_quote_source": "callback",
            },
        )

        quote_event = next(event for event in bus.events if event[0] == "market_quote")
        self.assertEqual(quote_event[2]["quote_source"], "callback")
        self.assertNotIn("__qmt_quote_source", quote_event[1])

    def test_quote_callback_updates_latest_quote_cache_and_diagnostics(self) -> None:
        service = MarketSubscriptionService(
            adapter=RecordingAdapter(),
            event_bus=RecordingBus(),
            id_factory=lambda: "sub_test",
        )
        service.create(symbols=["000001.SZ"], period="tick")

        service.handle_quote(
            "sub_test",
            {
                "schema": "market.quote.v1",
                "symbol": "000001.SZ",
                "last_price": 10.25,
                "__qmt_quote_source": "callback",
            },
        )

        latest = service.latest_quotes(["000001.SZ", "600000.SH"])
        diagnostics = service.diagnostics("sub_test")

        self.assertEqual(latest["quotes"][0]["symbol"], "000001.SZ")
        self.assertEqual(latest["quotes"][0]["quote"]["last_price"], 10.25)
        self.assertEqual(latest["quotes"][0]["quote_source"], "callback")
        self.assertEqual(latest["quotes"][0]["subscription_id"], "sub_test")
        self.assertEqual(latest["missing_symbols"], ["600000.SH"])
        self.assertEqual(diagnostics["callback_count"], 1)
        self.assertEqual(diagnostics["initial_quote_count"], 0)
        self.assertEqual(diagnostics["last_quote_source"], "callback")
        self.assertEqual(diagnostics["active_symbols"], ["000001.SZ"])

    def test_initial_and_callback_quotes_have_monotonic_event_sequence(self) -> None:
        bus = RecordingBus()
        service = MarketSubscriptionService(
            adapter=InitialQuoteAdapter(),
            event_bus=bus,
            id_factory=lambda: "sub_test",
        )

        service.create(symbols=["000001.SZ"], period="tick")
        service.handle_quote(
            "sub_test",
            {
                "schema": "market.quote.v1",
                "symbol": "000001.SZ",
                "last_price": 10.26,
                "__qmt_quote_source": "callback",
            },
        )

        quote_events = [event for event in bus.events if event[0] == "market_quote"]
        self.assertEqual(quote_events[0][2]["event_seq"], 1)
        self.assertEqual(quote_events[1][2]["event_seq"], 2)
        diagnostics = service.diagnostics("sub_test")
        self.assertEqual(diagnostics["initial_quote_count"], 1)
        self.assertEqual(diagnostics["callback_count"], 1)

    def test_stopped_subscription_does_not_update_latest_quote_cache_or_diagnostics(self) -> None:
        service = MarketSubscriptionService(
            adapter=RecordingAdapter(),
            event_bus=RecordingBus(),
            id_factory=lambda: "sub_test",
        )
        service.create(symbols=["000001.SZ"], period="tick")
        service.handle_quote(
            "sub_test",
            {
                "schema": "market.quote.v1",
                "symbol": "000001.SZ",
                "last_price": 10.25,
                "__qmt_quote_source": "callback",
            },
        )
        service.stop("sub_test")

        service.handle_quote(
            "sub_test",
            {
                "schema": "market.quote.v1",
                "symbol": "000001.SZ",
                "last_price": 99.99,
                "__qmt_quote_source": "callback",
            },
        )

        latest = service.latest_quotes(["000001.SZ"])
        diagnostics = service.diagnostics("sub_test")
        self.assertEqual(latest["quotes"][0]["quote"]["last_price"], 10.25)
        self.assertEqual(diagnostics["callback_count"], 1)
        self.assertEqual(diagnostics["status"], "stopped")

    def test_diagnostics_reports_quote_freshness_times(self) -> None:
        times = iter(
            [
                datetime(2026, 5, 28, 1, 0, 0, tzinfo=UTC),
                datetime(2026, 5, 28, 1, 0, 0, tzinfo=UTC),
                datetime(2026, 5, 28, 1, 0, 1, tzinfo=UTC),
                datetime(2026, 5, 28, 1, 0, 3, tzinfo=UTC),
                datetime(2026, 5, 28, 1, 0, 8, tzinfo=UTC),
            ]
        )
        service = MarketSubscriptionService(
            adapter=RecordingAdapter(),
            event_bus=RecordingBus(),
            id_factory=lambda: "sub_test",
            now_factory=lambda: next(times),
            callback_stale_after_seconds=10,
        )
        service.create(symbols=["000001.SZ"], period="tick")

        service.handle_quote(
            "sub_test",
            {
                "schema": "market.quote.v1",
                "symbol": "000001.SZ",
                "last_price": 10.25,
                "__qmt_quote_source": "initial",
            },
        )
        service.handle_quote(
            "sub_test",
            {
                "schema": "market.quote.v1",
                "symbol": "000001.SZ",
                "last_price": 10.26,
                "__qmt_quote_source": "callback",
            },
        )

        diagnostics = service.diagnostics("sub_test")

        self.assertEqual(diagnostics["last_initial_quote_at"], "2026-05-28T01:00:01+00:00")
        self.assertEqual(diagnostics["last_callback_at"], "2026-05-28T01:00:03+00:00")
        self.assertEqual(diagnostics["seconds_since_last_quote"], 5.0)
        self.assertEqual(diagnostics["seconds_since_last_callback"], 5.0)
        self.assertTrue(diagnostics["is_callback_active"])
        self.assertEqual(diagnostics["callback_stale_after_seconds"], 10)

    def test_create_marks_subscription_degraded_when_upstream_subscribe_fails(self) -> None:
        bus = RecordingBus()
        service = MarketSubscriptionService(
            adapter=FailingSubscribeAdapter(),
            event_bus=bus,
            id_factory=lambda: "sub_test",
        )

        subscription = service.create(symbols=["000001.SZ"], period="tick")
        diagnostics = service.diagnostics("sub_test")

        self.assertEqual(subscription.status, "degraded")
        self.assertIn("quote disconnected", subscription.last_error or "")
        self.assertEqual(diagnostics["status"], "degraded")
        self.assertEqual(diagnostics["degraded_reason"], "RuntimeError: quote disconnected")
        self.assertEqual(bus.events[-1][0], "market_subscription")
        self.assertEqual(bus.events[-1][1]["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
