from __future__ import annotations

import unittest

from qmtserver.market.normalizers import normalize_daily_bars, normalize_intraday_bars


class TableLike:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records

    def to_dict(self, orient: str = "records") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError("unsupported orient")
        return self.records


class MarketNormalizerTests(unittest.TestCase):
    def test_daily_normalizer_converts_symbol_mapping(self) -> None:
        bars = normalize_daily_bars(
            {
                "000001.SZ": [
                    {
                        "date": "2026-01-02",
                        "open": 10.1,
                        "high": 10.5,
                        "low": 10.0,
                        "close": 10.3,
                        "volume": 1200000,
                        "amount": 12345678.9,
                    }
                ]
            }
        )

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["date"], "2026-01-02")
        self.assertEqual(bars[0]["symbol"], "000001.SZ")
        self.assertEqual(bars[0]["open"], 10.1)
        self.assertEqual(bars[0]["volume"], 1200000)
        self.assertEqual(bars[0]["meta"], {})

    def test_intraday_normalizer_converts_table_like_records(self) -> None:
        bars = normalize_intraday_bars(
            TableLike(
                [
                    {
                        "timestamp": "2026-01-02T09:31:00+08:00",
                        "symbol": "000001.SZ",
                        "open": 10.1,
                        "high": 10.2,
                        "low": 10.0,
                        "close": 10.15,
                        "vol": 1000,
                        "amount": 10150.0,
                    }
                ]
            ),
            period="1m",
        )

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["timestamp"], "2026-01-02T09:31:00+08:00")
        self.assertEqual(bars[0]["symbol"], "000001.SZ")
        self.assertEqual(bars[0]["period"], "1m")
        self.assertEqual(bars[0]["volume"], 1000)

    def test_normalizers_return_empty_list_for_empty_data(self) -> None:
        self.assertEqual(normalize_daily_bars({}), [])
        self.assertEqual(normalize_intraday_bars([], period="1m"), [])


if __name__ == "__main__":
    unittest.main()
