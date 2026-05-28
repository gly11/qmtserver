from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from qmtserver.market.models import MarketRequest


class TargetProvider(Protocol):
    def get_target(self, target: str) -> Any: ...


class XtDataMarketAdapter:
    def __init__(self, provider: TargetProvider) -> None:
        self.provider = provider

    def fetch_daily(self, request: MarketRequest) -> Any:
        return self._get_market_data(request, period="1d")

    def fetch_intraday(self, request: MarketRequest) -> Any:
        assert request.period is not None
        return self._get_market_data(request, period=request.period)

    def download_history(self, request: MarketRequest) -> Any:
        assert request.period is not None
        xtdata = self.provider.get_target("xtdata")
        start_time = _xtdata_time(request.start)
        end_time = _xtdata_time(request.end)
        single_download = xtdata.download_history_data
        results = []
        for symbol in request.symbols:
            results.append(
                single_download(
                    stock_code=symbol,
                    period=request.period,
                    start_time=start_time,
                    end_time=end_time,
                    incrementally=None,
                )
            )
        return results

    def _get_market_data(self, request: MarketRequest, *, period: str) -> Any:
        xtdata = self.provider.get_target("xtdata")
        return xtdata.get_market_data_ex(
            field_list=[],
            stock_list=request.symbols,
            period=period,
            start_time=_xtdata_time(request.start),
            end_time=_xtdata_time(request.end),
            dividend_type=request.adjust,
        )


def _xtdata_time(value: str | None) -> str:
    if not value:
        return ""
    if value.isdigit():
        return value
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if "T" in value:
            return parsed.strftime("%Y%m%d%H%M%S")
        return parsed.strftime("%Y%m%d")
    return value
