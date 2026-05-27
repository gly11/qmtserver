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
    def test_smoke_ok_accepts_initial_quote_when_callback_not_required(self) -> None:
        module = load_smoke_module()
        result = {
            "quote_connected": True,
            "created": {"ok": True},
            "stopped_status": "stopped",
            "received_quote": True,
            "received_callback": False,
        }

        self.assertTrue(module.smoke_ok(result, require_callback=False))

    def test_smoke_ok_requires_callback_when_requested(self) -> None:
        module = load_smoke_module()
        result = {
            "quote_connected": True,
            "created": {"ok": True},
            "stopped_status": "stopped",
            "received_quote": True,
            "received_callback": False,
        }

        self.assertFalse(module.smoke_ok(result, require_callback=True))

    def test_summarize_event_keeps_quote_source(self) -> None:
        module = load_smoke_module()
        summary = module.summarize_event(
            {
                "type": "market_quote",
                "data": {"schema": "market.quote.v1", "symbol": "000001.SZ"},
                "meta": {"quote_source": "callback"},
            }
        )

        self.assertEqual(summary["type"], "market_quote")
        self.assertEqual(summary["quote_source"], "callback")


if __name__ == "__main__":
    unittest.main()
