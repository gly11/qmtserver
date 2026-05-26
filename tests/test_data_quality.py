from __future__ import annotations

import unittest

from qmtserver.data_quality.checks import quality_report
from qmtserver.data_quality.models import QUALITY_SCHEMA


class DataQualityTests(unittest.TestCase):
    def test_quality_report_detects_missing_duplicates_and_anomalies(self) -> None:
        report = quality_report(
            [
                {
                    "date": "2026-01-01",
                    "symbol": "000001.SZ",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.9,
                    "close": 10.2,
                    "volume": 100,
                },
                {
                    "date": "2026-01-01",
                    "symbol": "000001.SZ",
                    "open": -1.0,
                    "high": 9.0,
                    "low": 10.0,
                    "close": 9.5,
                    "volume": -10,
                },
            ],
            expected_dates=["2026-01-01", "2026-01-02"],
        )

        self.assertEqual(report["schema"], QUALITY_SCHEMA)
        self.assertEqual(report["missing_dates"], [{"symbol": "000001.SZ", "date": "2026-01-02"}])
        self.assertEqual(len(report["duplicate_rows"]), 1)
        self.assertEqual(len(report["price_anomalies"]), 1)
        self.assertEqual(len(report["volume_anomalies"]), 1)


if __name__ == "__main__":
    unittest.main()
