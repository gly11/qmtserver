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

    def test_reports_gap_when_segments_do_not_cover_middle_of_request(self) -> None:
        repository = FakeCoverageRepository(
            [
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-31",
                    "row_count": 20,
                    "file_count": 2,
                }
            ],
            segments=[
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-10",
                    "row_count": 8,
                    "file_count": 1,
                },
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-12",
                    "coverage_end": "2026-01-31",
                    "row_count": 12,
                    "file_count": 1,
                },
            ],
        )
        planner = CoveragePlanner(repository)

        result = planner.coverage(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "adjust": "none",
            }
        )

        self.assertFalse(result["fully_covered"])
        self.assertEqual(result["missing_symbols"], ["000001.SZ"])
        self.assertEqual(
            result["gaps"],
            [
                {
                    "symbol": "000001.SZ",
                    "gap_start": "2026-01-11",
                    "gap_end": "2026-01-11",
                    "reason": "segment_gap",
                }
            ],
        )

    def test_gap_explains_when_symbol_has_no_matching_segments(self) -> None:
        planner = CoveragePlanner(FakeCoverageRepository([]))

        result = planner.coverage(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "adjust": "none",
            }
        )

        self.assertEqual(
            result["gaps"],
            [
                {
                    "symbol": "000001.SZ",
                    "gap_start": "2026-01-01",
                    "gap_end": "2026-01-31",
                    "reason": "no_matching_coverage",
                }
            ],
        )

    def test_treats_overlapping_segments_as_fully_covered(self) -> None:
        repository = FakeCoverageRepository(
            [
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-31",
                    "row_count": 25,
                    "file_count": 2,
                }
            ],
            segments=[
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-15",
                    "row_count": 12,
                    "file_count": 1,
                },
                {
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-10",
                    "coverage_end": "2026-01-31",
                    "row_count": 13,
                    "file_count": 1,
                },
            ],
        )
        planner = CoveragePlanner(repository)

        result = planner.coverage(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "adjust": "none",
            }
        )

        self.assertTrue(result["fully_covered"])
        self.assertEqual(result["missing_symbols"], [])
        self.assertEqual(result["gaps"], [])
        self.assertEqual(len(result["covered_segments"]), 2)


class FakeCoverageRepository:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        segments: list[dict[str, Any]] | None = None,
    ) -> None:
        self.rows = rows
        self.segments = segments if segments is not None else rows
        self.requests: list[dict[str, Any]] = []

    def list_coverage(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        self.requests.append(request)
        return self.rows

    def list_coverage_segments(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        self.requests.append(request)
        return self.segments


if __name__ == "__main__":
    unittest.main()
