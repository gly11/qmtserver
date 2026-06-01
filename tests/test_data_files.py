from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from qmtserver.data.files import ParquetBarWriter


class ParquetBarWriterTests(unittest.TestCase):
    def test_write_bars_partitions_files_by_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parquet = FakeParquetModule()
            writer = ParquetBarWriter(
                Path(tmp),
                import_module=FakeImportModule(parquet),
            )
            files = writer.write_bars(
                {
                    "kind": "daily_bars",
                    "period": "1d",
                    "adjust": "none",
                    "start": "2026-01-01",
                    "end": "2026-01-31",
                },
                [
                    {"symbol": "000001.SZ", "date": "2026-01-02", "close": 10.3},
                    {"symbol": "600000.SH", "date": "2026-01-02", "close": 8.1},
                    {"symbol": "000001.SZ", "date": "2026-01-03", "close": 10.4},
                ],
            )

        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]["symbol"], "000001.SZ")
        self.assertEqual(files[0]["row_count"], 2)
        self.assertEqual(files[0]["coverage_start"], "2026-01-02")
        self.assertEqual(files[0]["coverage_end"], "2026-01-03")
        self.assertIn("symbol=000001.SZ", files[0]["path"])
        self.assertTrue(files[0]["hash"].startswith("sha256:"))
        self.assertEqual(len(parquet.writes), 2)


class FakeImportModule:
    def __init__(self, parquet: FakeParquetModule) -> None:
        self.parquet = parquet
        self.pyarrow = FakePyArrowModule()

    def __call__(self, name: str) -> object:
        if name == "pyarrow":
            return self.pyarrow
        if name == "pyarrow.parquet":
            return self.parquet
        raise ModuleNotFoundError(name)


class FakePyArrowModule:
    class Table:
        @staticmethod
        def from_pylist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return rows


class FakeParquetModule:
    def __init__(self) -> None:
        self.writes: list[tuple[object, Path]] = []

    def write_table(self, table: object, path: Path) -> None:
        self.writes.append((table, path))
        path.write_text("fake parquet", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
