from __future__ import annotations

import importlib.util
import unittest
from datetime import date as date_cls
from pathlib import Path
from typing import Any
from unittest.mock import patch


def load_smoke_module() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_market_data_lake.py"
    spec = importlib.util.spec_from_file_location("smoke_market_data_lake", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load smoke script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MarketDataLakeSmokeScriptTests(unittest.TestCase):
    def test_script_paths_are_readonly_data_lake_paths(self) -> None:
        module = load_smoke_module()

        paths = " ".join(module.READONLY_PATHS).lower()

        self.assertIn("/v1/market/data/download", paths)
        self.assertIn("/v1/market/data/bars", paths)
        self.assertIn("/v1/market/data/exports", paths)
        self.assertNotRegex(paths, r"/trader|order|cancel|transfer")

    def test_summarize_job_response_omits_files_and_paths(self) -> None:
        module = load_smoke_module()

        summary = module.summarize_job_response(
            {
                "ok": True,
                "data": {
                    "job": {
                        "job_id": "job-1",
                        "status": "succeeded",
                        "result": {
                            "downloaded": True,
                            "cached": False,
                            "row_count": 10,
                            "file_count": 1,
                            "files": [{"path": "C:/private/file.parquet"}],
                        },
                    }
                },
                "error": None,
            }
        )

        self.assertEqual(summary["job_id"], "job-1")
        self.assertEqual(summary["row_count"], 10)
        self.assertNotIn("files", summary)
        self.assertNotIn("path", str(summary).lower())

    def test_smoke_ok_requires_all_readonly_steps_and_cached_second_download(self) -> None:
        module = load_smoke_module()
        result = {
            "trader_connected": False,
            "health": {"ok": True},
            "download_job": {"ok": True, "row_count": 10},
            "coverage": {"ok": True, "fully_covered": True},
            "bars": {"ok": True, "row_count": 10},
            "quality": {"ok": True},
            "export": {"ok": True, "row_count": 10},
            "cached_download_job": {"ok": True, "cached": True, "row_count": 10},
        }

        self.assertTrue(module.smoke_ok(result, require_rows=True))
        result["cached_download_job"]["cached"] = False
        self.assertFalse(module.smoke_ok(result, require_rows=True))

    def test_default_window_ends_on_previous_day(self) -> None:
        module = load_smoke_module()

        class FakeDateTime:
            @classmethod
            def now(cls) -> Any:
                return FakeNow()

        class FakeNow:
            def date(self) -> date_cls:
                return date_cls(2026, 6, 3)

        with patch.object(module, "datetime", FakeDateTime):
            window = module._default_window()

        self.assertEqual(window, {"start": "2026-05-26", "end": "2026-06-02"})


if __name__ == "__main__":
    unittest.main()
