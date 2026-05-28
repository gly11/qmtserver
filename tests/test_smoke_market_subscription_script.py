from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any


def load_smoke_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_market_subscription.py"
    spec = importlib.util.spec_from_file_location("smoke_market_subscription", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load smoke script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MarketSubscriptionSmokeScriptTests(unittest.TestCase):
    def test_parser_accepts_symbols_and_keeps_symbol_compatibility(self) -> None:
        module = load_smoke_module()

        batch_args = module.build_parser().parse_args(["--symbols", "000001.SZ, 600000.SH"])
        legacy_args = module.build_parser().parse_args(["--symbol", "510300.SH"])
        post_stop_args = module.build_parser().parse_args(["--post-stop-listen-seconds", "3"])
        long_args = module.build_parser().parse_args(
            [
                "--duration-seconds",
                "120",
                "--min-callbacks",
                "3",
                "--report-intervals",
                "--omit-events",
            ]
        )

        self.assertEqual(module.symbols_from_args(batch_args), ["000001.SZ", "600000.SH"])
        self.assertEqual(module.symbols_from_args(legacy_args), ["510300.SH"])
        self.assertEqual(post_stop_args.post_stop_listen_seconds, 3.0)
        self.assertEqual(long_args.duration_seconds, 120.0)
        self.assertEqual(long_args.min_callbacks, 3)
        self.assertTrue(long_args.report_intervals)
        self.assertTrue(long_args.omit_events)

    def test_omit_events_replaces_event_list_with_count(self) -> None:
        module = load_smoke_module()
        result = {
            "events": [{"type": "market_quote"}, {"type": "heartbeat"}],
            "post_stop_events": [{"type": "heartbeat"}],
            "callback_count": 1,
        }

        pruned = module.prune_result(result, omit_events=True)

        self.assertNotIn("events", pruned)
        self.assertEqual(pruned["event_count"], 2)
        self.assertNotIn("post_stop_events", pruned)
        self.assertEqual(pruned["post_stop_event_count"], 1)
        self.assertEqual(result["events"], [{"type": "market_quote"}, {"type": "heartbeat"}])

    def test_smoke_ok_accepts_initial_quote_when_callback_not_required(self) -> None:
        module = load_smoke_module()
        result = {
            "symbols": ["000001.SZ"],
            "quote_connected": True,
            "created": {"ok": True},
            "stopped_status": "stopped",
            "received_quote": True,
            "received_callback": False,
            "latest_cache_hit": True,
            "cache_hit_symbols": ["000001.SZ"],
            "diagnostics_ok": True,
            "post_stop_market_quote_events": 0,
            "callback_count": 0,
            "min_callbacks": 0,
        }

        self.assertTrue(module.smoke_ok(result, require_callback=False, require_all_symbols=False))

    def test_smoke_ok_requires_callback_when_requested(self) -> None:
        module = load_smoke_module()
        result = {
            "symbols": ["000001.SZ"],
            "quote_connected": True,
            "created": {"ok": True},
            "stopped_status": "stopped",
            "received_quote": True,
            "received_callback": False,
            "latest_cache_hit": True,
            "cache_hit_symbols": ["000001.SZ"],
            "diagnostics_ok": True,
            "post_stop_market_quote_events": 0,
            "callback_count": 0,
            "min_callbacks": 0,
        }

        self.assertFalse(module.smoke_ok(result, require_callback=True, require_all_symbols=False))

    def test_summarize_event_keeps_quote_source(self) -> None:
        module = load_smoke_module()
        summary = module.summarize_event(
            {
                "type": "market_quote",
                "data": {"schema": "market.quote.v1", "symbol": "000001.SZ"},
                "meta": {"quote_source": "callback", "event_seq": 7},
            }
        )

        self.assertEqual(summary["type"], "market_quote")
        self.assertEqual(summary["quote_source"], "callback")
        self.assertEqual(summary["event_seq"], 7)

    def test_smoke_ok_requires_latest_cache_and_diagnostics(self) -> None:
        module = load_smoke_module()
        result = {
            "symbols": ["000001.SZ"],
            "quote_connected": True,
            "created": {"ok": True},
            "stopped_status": "stopped",
            "received_quote": True,
            "received_callback": True,
            "latest_cache_hit": False,
            "cache_hit_symbols": [],
            "diagnostics_ok": True,
            "post_stop_market_quote_events": 0,
            "callback_count": 1,
            "min_callbacks": 0,
        }

        self.assertFalse(module.smoke_ok(result, require_callback=True, require_all_symbols=False))

    def test_smoke_ok_can_require_all_symbols_in_latest_cache(self) -> None:
        module = load_smoke_module()
        result = {
            "symbols": ["000001.SZ", "600000.SH"],
            "quote_connected": True,
            "created": {"ok": True},
            "stopped_status": "stopped",
            "received_quote": True,
            "received_callback": True,
            "latest_cache_hit": True,
            "cache_hit_symbols": ["000001.SZ"],
            "diagnostics_ok": True,
            "post_stop_market_quote_events": 0,
            "callback_count": 1,
            "min_callbacks": 0,
        }

        self.assertFalse(module.smoke_ok(result, require_callback=True, require_all_symbols=True))

        result["cache_hit_symbols"] = ["000001.SZ", "600000.SH"]
        self.assertTrue(module.smoke_ok(result, require_callback=True, require_all_symbols=True))

    def test_smoke_ok_rejects_post_stop_market_quotes(self) -> None:
        module = load_smoke_module()
        result = {
            "symbols": ["000001.SZ"],
            "quote_connected": True,
            "created": {"ok": True},
            "stopped_status": "stopped",
            "received_quote": True,
            "received_callback": True,
            "latest_cache_hit": True,
            "cache_hit_symbols": ["000001.SZ"],
            "diagnostics_ok": True,
            "post_stop_market_quote_events": 1,
            "callback_count": 1,
            "min_callbacks": 0,
        }

        self.assertFalse(module.smoke_ok(result, require_callback=True, require_all_symbols=False))

    def test_smoke_ok_enforces_min_callbacks(self) -> None:
        module = load_smoke_module()
        result = {
            "symbols": ["000001.SZ"],
            "quote_connected": True,
            "created": {"ok": True},
            "stopped_status": "stopped",
            "received_quote": True,
            "received_callback": True,
            "latest_cache_hit": True,
            "cache_hit_symbols": ["000001.SZ"],
            "diagnostics_ok": True,
            "post_stop_market_quote_events": 0,
            "callback_count": 2,
            "min_callbacks": 3,
        }

        self.assertFalse(module.smoke_ok(result, require_callback=True, require_all_symbols=False))

        result["callback_count"] = 3
        self.assertTrue(module.smoke_ok(result, require_callback=True, require_all_symbols=False))

    def test_callback_report_counts_symbols_and_intervals(self) -> None:
        module = load_smoke_module()
        events = [
            {"type": "market_quote", "symbol": "000001.SZ", "quote_source": "callback"},
            {"type": "market_quote", "symbol": "600000.SH", "quote_source": "initial"},
            {"type": "market_quote", "symbol": "000001.SZ", "quote_source": "callback"},
        ]

        report = module.callback_report(events, elapsed_seconds=5.5)

        self.assertEqual(report["callback_count"], 2)
        self.assertEqual(report["callback_symbols"], {"000001.SZ": 2})
        self.assertEqual(report["elapsed_seconds"], 5.5)

    def test_summarize_latest_reports_cache_hit_symbols(self) -> None:
        module = load_smoke_module()
        summary = module.summarize_latest(
            {
                "ok": True,
                "data": {
                    "quotes": [{"symbol": "000001.SZ"}, {"symbol": "600000.SH"}],
                    "missing_symbols": ["510300.SH"],
                },
            }
        )

        self.assertEqual(summary["cache_hit_symbols"], ["000001.SZ", "600000.SH"])
        self.assertEqual(summary["missing_symbols"], ["510300.SH"])

    def test_summarize_diagnostics_keeps_freshness_fields(self) -> None:
        module = load_smoke_module()
        summary = module.summarize_diagnostics(
            {
                "ok": True,
                "data": {
                    "subscription_id": "sub_test",
                    "last_callback_at": "2026-05-28T01:00:03+00:00",
                    "seconds_since_last_callback": 2.5,
                    "is_callback_active": True,
                },
            }
        )

        self.assertEqual(summary["last_callback_at"], "2026-05-28T01:00:03+00:00")
        self.assertEqual(summary["seconds_since_last_callback"], 2.5)
        self.assertTrue(summary["is_callback_active"])

    def test_receive_events_records_receiver_errors(self) -> None:
        module = load_smoke_module()

        class BrokenWebSocket:
            def receive_json(self) -> dict[str, object]:
                raise RuntimeError("closed")

        result = {"received_quote": False, "received_callback": False}
        events: list[dict[str, object]] = []

        module._receive_events(BrokenWebSocket(), events, result, require_callback=True)

        self.assertEqual(events, [])
        self.assertEqual(result["receiver_error"], "RuntimeError: closed")


if __name__ == "__main__":
    unittest.main()
