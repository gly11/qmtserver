from __future__ import annotations

import unittest
from typing import Any

from qmtserver.market.adapter import XtDataMarketAdapter
from qmtserver.market.models import MarketRequest
from qmtserver.market.subscription_adapter import XtDataSubscriptionAdapter


class RecordingXtData:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.subscribe_calls: list[dict[str, Any]] = []
        self.unsubscribe_calls: list[int] = []

    def get_market_data_ex(self, **kwargs: Any) -> dict[str, list[dict[str, object]]]:
        self.calls.append(kwargs)
        return {}

    def subscribe_quote(self, **kwargs: Any) -> int:
        self.subscribe_calls.append(kwargs)
        return len(self.subscribe_calls)

    def unsubscribe_quote(self, seq: int) -> None:
        self.unsubscribe_calls.append(seq)


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


class MarketSubscriptionAdapterTests(unittest.TestCase):
    def test_subscribe_quote_calls_upstream_once_per_symbol(self) -> None:
        provider = RecordingProvider()
        adapter = XtDataSubscriptionAdapter(provider)

        upstream_ids = adapter.subscribe(
            symbols=["000001.SZ", "600000.SH"],
            period="tick",
            callback=lambda payload: None,
        )

        self.assertEqual(upstream_ids, [1, 2])
        self.assertEqual(len(provider.xtdata.subscribe_calls), 2)
        first = provider.xtdata.subscribe_calls[0]
        self.assertEqual(first["stock_code"], "000001.SZ")
        self.assertEqual(first["period"], "tick")
        self.assertEqual(first["start_time"], "")
        self.assertEqual(first["end_time"], "")
        self.assertEqual(first["count"], 0)
        self.assertTrue(callable(first["callback"]))

    def test_unsubscribe_quote_accepts_multiple_upstream_ids(self) -> None:
        provider = RecordingProvider()
        adapter = XtDataSubscriptionAdapter(provider)

        adapter.unsubscribe([3, 5])

        self.assertEqual(provider.xtdata.unsubscribe_calls, [3, 5])

    def test_subscribe_quote_normalizes_callback_payloads(self) -> None:
        provider = RecordingProvider()
        adapter = XtDataSubscriptionAdapter(provider)
        received: list[dict[str, Any]] = []

        adapter.subscribe(
            symbols=["000001.SZ"],
            period="tick",
            callback=received.append,
        )
        upstream_callback = provider.xtdata.subscribe_calls[0]["callback"]

        upstream_callback({"000001.SZ": {"lastPrice": 10.25, "volume": 1200}})

        self.assertEqual(received[0]["schema"], "market.quote.v1")
        self.assertEqual(received[0]["symbol"], "000001.SZ")
        self.assertEqual(received[0]["last_price"], 10.25)


if __name__ == "__main__":
    unittest.main()
