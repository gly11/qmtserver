from __future__ import annotations

import unittest

from qmtserver.data.chunks import plan_download_chunks


class DataChunkPlannerTests(unittest.TestCase):
    def test_plans_daily_chunks_by_symbol_and_date_window(self) -> None:
        chunks = plan_download_chunks(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ", "600000.SH"],
                "start": "2026-01-01",
                "end": "2026-02-15",
                "adjust": "none",
                "chunk_days": 31,
            }
        )

        self.assertEqual(
            [(chunk["symbol"], chunk["chunk_start"], chunk["chunk_end"]) for chunk in chunks],
            [
                ("000001.SZ", "2026-01-01", "2026-01-31"),
                ("000001.SZ", "2026-02-01", "2026-02-15"),
                ("600000.SH", "2026-01-01", "2026-01-31"),
                ("600000.SH", "2026-02-01", "2026-02-15"),
            ],
        )
        self.assertEqual(chunks[0]["status"], "queued")
        self.assertEqual(chunks[0]["attempts"], 0)
        self.assertEqual(chunks[0]["period"], "1d")

    def test_plans_single_chunk_when_dates_are_missing(self) -> None:
        chunks = plan_download_chunks(
            {
                "kind": "daily_bars",
                "symbols": ["000001.SZ"],
                "adjust": "none",
            }
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["symbol"], "000001.SZ")
        self.assertIsNone(chunks[0]["chunk_start"])
        self.assertIsNone(chunks[0]["chunk_end"])


if __name__ == "__main__":
    unittest.main()
