from __future__ import annotations

import unittest
from typing import Any

from qmtserver.data.coverage import CoveragePlanner


class CoveragePlannerTests(unittest.TestCase):
    def test_reports_request_fully_covered_when_each_symbol_range_is_available(self) -> None:
        repository = FakeCoverageRepository(
            [
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-31",
                    "row_count": 20,
                    "file_count": 1,
                },
                {
                    "symbol": "600000.SH",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-31",
                    "row_count": 19,
                    "file_count": 1,
                },
            ]
        )
        planner = CoveragePlanner(repository)

        result = planner.coverage(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ", "600000.SH"],
                "start": "2026-01-05",
                "end": "2026-01-20",
                "adjust": "none",
            }
        )

        self.assertTrue(result["fully_covered"])
        self.assertEqual(result["missing_symbols"], [])
        self.assertEqual(len(result["coverage"]), 2)

    def test_reports_missing_symbols_when_any_requested_symbol_is_not_covered(self) -> None:
        repository = FakeCoverageRepository(
            [
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-10",
                    "row_count": 5,
                    "file_count": 1,
                }
            ]
        )
        planner = CoveragePlanner(repository)

        result = planner.coverage(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ", "600000.SH"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "adjust": "none",
            }
        )

        self.assertFalse(result["fully_covered"])
        self.assertEqual(result["missing_symbols"], ["000001.SZ", "600000.SH"])


class FakeCoverageRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.requests: list[dict[str, Any]] = []

    def list_coverage(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        self.requests.append(request)
        return self.rows


if __name__ == "__main__":
    unittest.main()
