from __future__ import annotations

import unittest
from typing import Any

from qmtserver.market.adapter import XtDataMarketAdapter
from qmtserver.market.models import MarketRequest


class RecordingXtData:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_market_data_ex(self, **kwargs: Any) -> dict[str, list[dict[str, object]]]:
        self.calls.append(kwargs)
        return {}


class RecordingProvider:
    def __init__(self) -> None:
        self.xtdata = RecordingXtData()

    def get_target(self, target: str) -> RecordingXtData:
        self.assert_target = target
        return self.xtdata


class MarketAdapterTests(unittest.TestCase):
    def test_daily_bars_convert_iso_dates_for_xtdata(self) -> None:
        provider = RecordingProvider()
        adapter = XtDataMarketAdapter(provider)

        adapter.fetch_daily(
            MarketRequest(
                symbols=["000001.SZ"],
                start="2026-05-25",
                end="2026-05-26",
                adjust="none",
            )
        )

        call = provider.xtdata.calls[0]
        self.assertEqual(call["start_time"], "20260525")
        self.assertEqual(call["end_time"], "20260526")

    def test_intraday_bars_convert_iso_datetimes_for_xtdata(self) -> None:
        provider = RecordingProvider()
        adapter = XtDataMarketAdapter(provider)

        adapter.fetch_intraday(
            MarketRequest(
                symbols=["000001.SZ"],
                start="2026-05-26T09:30:00+08:00",
                end="2026-05-26T15:00:00+08:00",
                adjust="none",
                period="1m",
            )
        )

        call = provider.xtdata.calls[0]
        self.assertEqual(call["start_time"], "20260526093000")
        self.assertEqual(call["end_time"], "20260526150000")


if __name__ == "__main__":
    unittest.main()
