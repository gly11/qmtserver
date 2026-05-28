from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any


def load_smoke_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_market_history.py"
    spec = importlib.util.spec_from_file_location("smoke_market_history", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load smoke script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MarketHistorySmokeScriptTests(unittest.TestCase):
    def test_summarize_bars_response_counts_rows_without_raw_bars(self) -> None:
        module = load_smoke_module()

        summary = module.summarize_bars_response(
            "daily",
            {
                "ok": True,
                "data": {"bars": [{"symbol": "000001.SZ"}, {"symbol": "600000.SH"}]},
                "meta": {
                    "schema": "market.bars.v1",
                    "request": {"symbols": ["000001.SZ", "600000.SH"]},
                    "row_count": 2,
                },
                "error": None,
            },
        )

        self.assertEqual(summary["name"], "daily")
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["row_count"], 2)
        self.assertEqual(summary["symbols"], ["000001.SZ", "600000.SH"])
        self.assertNotIn("bars", summary)

    def test_summarize_snapshot_response_omits_paths_and_hashes(self) -> None:
        module = load_smoke_module()

        summary = module.summarize_snapshot_response(
            {
                "ok": True,
                "data": {
                    "manifest": {
                        "snapshot_id": "daily_bars-abc",
                        "hash": "sha256:secret",
                        "row_count": 1,
                        "symbol_count": 1,
                        "format": "csv",
                    },
                    "cached": False,
                },
                "error": None,
            }
        )

        self.assertEqual(summary["snapshot_id"], "daily_bars-abc")
        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(summary["format"], "csv")
        self.assertNotIn("hash", summary)

    def test_smoke_ok_requires_quote_and_all_scopes_ok(self) -> None:
        module = load_smoke_module()
        result = {
            "quote_connected": True,
            "daily": {"ok": True, "row_count": 1},
            "intraday": {"ok": True, "row_count": 1},
            "quality": {"ok": True},
            "snapshot": {"ok": True, "row_count": 1},
            "job": {"ok": True, "row_count": 1},
            "intraday_job": {"ok": True, "row_count": 1},
        }

        self.assertTrue(module.smoke_ok(result))
        self.assertTrue(module.smoke_ok(result, require_rows=True))
        result["job"]["ok"] = False
        self.assertFalse(module.smoke_ok(result))

    def test_smoke_ok_can_require_non_empty_market_rows(self) -> None:
        module = load_smoke_module()
        result = {
            "quote_connected": True,
            "daily": {"ok": True, "row_count": 1},
            "intraday": {"ok": True, "row_count": 0},
            "quality": {"ok": True},
            "snapshot": {"ok": True, "row_count": 1},
            "job": {"ok": True, "row_count": 1},
            "intraday_job": {"ok": True, "row_count": 1},
        }

        self.assertTrue(module.smoke_ok(result))
        self.assertFalse(module.smoke_ok(result, require_rows=True))

    def test_smoke_ok_checks_intraday_download_job_when_present(self) -> None:
        module = load_smoke_module()
        result = {
            "quote_connected": True,
            "daily": {"ok": True, "row_count": 1},
            "intraday": {"ok": True, "row_count": 1},
            "quality": {"ok": True},
            "snapshot": {"ok": True, "row_count": 1},
            "job": {"ok": True, "row_count": 1},
            "intraday_job": {"ok": False, "row_count": 0},
        }

        self.assertFalse(module.smoke_ok(result))

    def test_script_scopes_are_readonly_market_paths(self) -> None:
        module = load_smoke_module()

        paths = " ".join(module.READONLY_PATHS).lower()

        self.assertIn("/v1/market/bars/daily", paths)
        self.assertIn("/v1/jobs/history-download", paths)
        self.assertIn("/v1/snapshots", paths)
        self.assertNotRegex(paths, r"/trader|order|cancel|transfer")


if __name__ == "__main__":
    unittest.main()
