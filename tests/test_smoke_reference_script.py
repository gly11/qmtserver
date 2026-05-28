from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any


def load_smoke_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_reference.py"
    spec = importlib.util.spec_from_file_location("smoke_reference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load smoke script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReferenceSmokeScriptTests(unittest.TestCase):
    def test_summarize_universe_counts_symbols_without_raw_list(self) -> None:
        module = load_smoke_module()

        summary = module.summarize_universe_response(
            {
                "ok": True,
                "data": {"name": "all_a", "symbols": ["000001.SZ", "600000.SH"]},
                "error": None,
                "meta": {"schema": "reference.universe.v1"},
            }
        )

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["symbol_count"], 2)
        self.assertNotIn("symbols", summary)

    def test_summarize_instruments_reports_observed_fields(self) -> None:
        module = load_smoke_module()

        summary = module.summarize_instruments_response(
            {
                "ok": True,
                "data": {
                    "instruments": [
                        {"symbol": "000001.SZ", "name": "Ping An", "ExchangeID": "SZ"},
                        {"symbol": "600000.SH", "name": "SPDB", "ExchangeID": "SH"},
                    ]
                },
                "error": None,
                "meta": {"schema": "reference.instruments.v1"},
            }
        )

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["instrument_count"], 2)
        self.assertIn("ExchangeID", summary["observed_fields"])
        self.assertNotIn("instruments", summary)

    def test_smoke_ok_requires_quote_and_reference_responses(self) -> None:
        module = load_smoke_module()
        result = {
            "quote_connected": True,
            "calendar": {"ok": True, "date_count": 2},
            "universe": {"ok": True, "symbol_count": 1},
            "instruments": {"ok": True, "instrument_count": 1},
        }

        self.assertTrue(module.smoke_ok(result))
        result["universe"]["symbol_count"] = 0
        self.assertFalse(module.smoke_ok(result))


if __name__ == "__main__":
    unittest.main()
