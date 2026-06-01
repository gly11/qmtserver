from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from qmtserver.data.exports import DataExportService


class DataExportServiceTests(unittest.TestCase):
    def test_create_export_writes_csv_and_manifest_from_local_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            query = FakeBarQuery(
                [
                    {
                        "date": "2026-01-02",
                        "symbol": "000001.SZ",
                        "open": 10.1,
                        "high": 10.5,
                        "low": 10.0,
                        "close": 10.3,
                        "volume": 1200,
                        "amount": 12345.0,
                        "meta": {},
                    }
                ]
            )
            service = DataExportService(query, root=Path(tmp))

            response = service.create(
                {
                    "kind": "daily_bars",
                    "symbols": ["000001.SZ"],
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                    "adjust": "none",
                    "format": "csv",
                }
            )
            manifest = response["data"]["manifest"]
            download_path = service.download_path(str(manifest["export_id"]))

        self.assertTrue(response["ok"])
        self.assertEqual(manifest["row_count"], 1)
        self.assertTrue(manifest["hash"].startswith("sha256:"))
        self.assertEqual(download_path.suffix, ".csv")
        self.assertEqual(query.requests[0]["symbols"], ["000001.SZ"])


class FakeBarQuery:
    def __init__(self, bars: list[dict[str, Any]]) -> None:
        self.bars = bars
        self.requests: list[dict[str, Any]] = []

    def query_bars(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        return {
            "schema": "market.data.bars.v1",
            "request": request,
            "bars": self.bars,
            "row_count": len(self.bars),
            "truncated": False,
        }


if __name__ == "__main__":
    unittest.main()
