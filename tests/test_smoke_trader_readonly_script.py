from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any


def load_smoke_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_trader_readonly.py"
    spec = importlib.util.spec_from_file_location("smoke_trader_readonly", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load smoke script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TraderReadonlySmokeScriptTests(unittest.TestCase):
    def test_summarize_response_redacts_account_and_counts_rows(self) -> None:
        module = load_smoke_module()

        summary = module.summarize_response(
            "asset",
            {
                "ok": True,
                "data": {"asset": {"account_id": "123456789", "cash": 100.0}},
                "meta": {"account_id": "123****789", "account_type": "STOCK"},
                "error": None,
            },
        )

        self.assertEqual(summary["name"], "asset")
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["account_id"], "123****789")
        self.assertNotIn("123456789", repr(summary))

    def test_summarize_response_counts_lists_without_raw_rows(self) -> None:
        module = load_smoke_module()

        summary = module.summarize_response(
            "positions",
            {
                "ok": True,
                "data": {"positions": [{"stock_code": "000001.SZ"}, {"stock_code": "600000.SH"}]},
                "meta": {"account_id": "***", "account_type": "STOCK"},
                "error": None,
            },
        )

        self.assertEqual(summary["row_count"], 2)
        self.assertNotIn("rows", summary)

    def test_smoke_ok_requires_every_endpoint_ok_and_trader_connected(self) -> None:
        module = load_smoke_module()
        result = {
            "trader_connected": True,
            "endpoints": [
                {"name": "account_status", "ok": True},
                {"name": "asset", "ok": True},
            ],
        }

        self.assertTrue(module.smoke_ok(result))
        result["endpoints"][1]["ok"] = False
        self.assertFalse(module.smoke_ok(result))

    def test_readonly_paths_do_not_include_trading_actions(self) -> None:
        module = load_smoke_module()

        paths = [endpoint.path for endpoint in module.READONLY_ENDPOINTS]

        self.assertEqual(
            paths,
            [
                "/v1/trader/account-status",
                "/v1/trader/asset",
                "/v1/trader/positions",
                "/v1/trader/orders",
                "/v1/trader/trades",
            ],
        )
        self.assertNotRegex(" ".join(paths).lower(), r"order-stock|cancel|transfer")


if __name__ == "__main__":
    unittest.main()
