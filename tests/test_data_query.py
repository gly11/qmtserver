from __future__ import annotations

import unittest
from typing import Any

from qmtserver.data.query import LocalBarQuery


class LocalBarQueryTests(unittest.TestCase):
    def test_query_bars_reads_registered_files_and_returns_limited_rows(self) -> None:
        repository = FakeFileRepository(
            [
                {
                    "path": "data/market/raw/bars/file-1.parquet",
                    "symbol": "000001.SZ",
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-01-31",
                }
            ]
        )
        reader = FakeParquetReader(
            [
                {"symbol": "000001.SZ", "date": "2026-01-02", "close": 10.3},
                {"symbol": "000001.SZ", "date": "2026-01-03", "close": 10.4},
            ]
        )
        query = LocalBarQuery(repository, reader=reader)

        response = query.query_bars(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "adjust": "none",
                "limit": 1,
            }
        )

        self.assertEqual(response["schema"], "market.data.bars.v1")
        self.assertEqual(response["row_count"], 1)
        self.assertTrue(response["truncated"])
        self.assertEqual(
            response["bars"],
            [{"symbol": "000001.SZ", "date": "2026-01-02", "close": 10.3}],
        )
        self.assertEqual(reader.files, repository.files)

    def test_query_bars_returns_empty_rows_when_no_files_are_registered(self) -> None:
        query = LocalBarQuery(FakeFileRepository([]), reader=FakeParquetReader([]))

        response = query.query_bars(
            {"kind": "daily_bars", "symbols": ["000001.SZ"], "adjust": "none"}
        )

        self.assertEqual(response["row_count"], 0)
        self.assertEqual(response["bars"], [])
        self.assertFalse(response["truncated"])

    def test_query_bars_sorts_deduplicates_and_offsets_rows(self) -> None:
        repository = FakeFileRepository(
            [
                {"path": "data/market/raw/bars/file-1.parquet"},
                {"path": "data/market/raw/bars/file-2.parquet"},
            ]
        )
        reader = FakeParquetReader(
            [
                {"symbol": "600000.SH", "date": "2026-01-03", "close": 9.2},
                {"symbol": "000001.SZ", "date": "2026-01-02", "close": 10.3},
                {"symbol": "000001.SZ", "date": "2026-01-02", "close": 10.3},
                {"symbol": "000001.SZ", "date": "2026-01-03", "close": 10.4},
            ]
        )
        query = LocalBarQuery(repository, reader=reader)

        response = query.query_bars(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ", "600000.SH"],
                "adjust": "none",
                "limit": 1,
                "offset": 1,
            }
        )

        self.assertEqual(response["row_count"], 1)
        self.assertEqual(response["total_row_count"], 3)
        self.assertEqual(response["deduplicated_row_count"], 1)
        self.assertTrue(response["truncated"])
        self.assertEqual(response["next_offset"], 2)
        self.assertEqual(
            response["bars"],
            [{"symbol": "000001.SZ", "date": "2026-01-03", "close": 10.4}],
        )


class FakeFileRepository:
    def __init__(self, files: list[dict[str, Any]]) -> None:
        self.files = files
        self.requests: list[dict[str, Any]] = []

    def list_files(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        self.requests.append(request)
        return self.files


class FakeParquetReader:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.files: list[dict[str, Any]] = []

    def read_bars(
        self,
        files: list[dict[str, Any]],
        request: dict[str, Any],
    ) -> list[dict[str, Any]]:
        del request
        self.files = files
        return self.rows


if __name__ == "__main__":
    unittest.main()
