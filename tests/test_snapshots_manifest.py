from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qmtserver.snapshots.manifest import request_hash
from qmtserver.snapshots.registry import SnapshotRegistry
from qmtserver.snapshots.writers import write_csv


class SnapshotManifestTests(unittest.TestCase):
    def test_request_hash_is_stable_for_equivalent_requests(self) -> None:
        first = {
            "kind": "daily_bars",
            "symbols": ["000001.SZ"],
            "start": "2026-01-01",
            "end": "2026-01-31",
            "adjust": "none",
            "format": "csv",
        }
        second = {
            "format": "csv",
            "adjust": "none",
            "end": "2026-01-31",
            "start": "2026-01-01",
            "symbols": ["000001.SZ"],
            "kind": "daily_bars",
        }

        self.assertEqual(request_hash(first), request_hash(second))

    def test_csv_writer_uses_stable_column_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bars.csv"
            digest = write_csv(
                path,
                [
                    {
                        "date": "2026-01-02",
                        "symbol": "000001.SZ",
                        "open": 10.1,
                        "high": 10.5,
                        "low": 10.0,
                        "close": 10.3,
                        "volume": 1200000,
                        "amount": 12345678.9,
                        "meta": {},
                    }
                ],
            )

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "date,symbol,open,high,low,close,volume,amount,meta")
            self.assertTrue(digest.startswith("sha256:"))

    def test_registry_lists_and_finds_manifest_by_request_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = SnapshotRegistry(Path(tmp))
            manifest = {
                "snapshot_id": "daily_bars-abc",
                "request_hash": "sha256:abc",
                "schema": "market.bars.v1",
                "format": "csv",
                "request": {"kind": "daily_bars"},
                "hash": "sha256:data",
                "row_count": 0,
                "symbol_count": 1,
                "coverage_start": None,
                "coverage_end": None,
                "generated_at": "2026-05-26T00:00:00+00:00",
                "qmtserver_version": "0.3.0",
                "xtquant_version": None,
            }

            registry.save(manifest)

            self.assertEqual(len(registry.list_manifests()), 1)
            self.assertEqual(registry.find_by_request_hash("sha256:abc"), manifest)


if __name__ == "__main__":
    unittest.main()
