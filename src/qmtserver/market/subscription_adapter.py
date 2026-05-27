from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qmtserver.errors import QmtMarketSubscriptionUnsupportedError
from qmtserver.market.adapter import TargetProvider
from qmtserver.market.normalizers import normalize_quote_payload


class XtDataSubscriptionAdapter:
    def __init__(self, provider: TargetProvider) -> None:
        self.provider = provider

    def subscribe(
        self,
        *,
        symbols: list[str],
        period: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> list[Any]:
        xtdata = self.provider.get_target("xtdata")
        upstream_ids: list[Any] = []
        for symbol in symbols:
            upstream_ids.append(
                xtdata.subscribe_quote(
                    stock_code=symbol,
                    period=period,
                    start_time="",
                    end_time="",
                    count=0,
                    callback=_quote_callback(symbol, callback),
                )
            )
        return upstream_ids

    def unsubscribe(self, upstream_id: Any) -> None:
        xtdata = self.provider.get_target("xtdata")
        unsubscribe = getattr(xtdata, "unsubscribe_quote", None)
        if not callable(unsubscribe):
            raise QmtMarketSubscriptionUnsupportedError("xtdata.unsubscribe_quote is not available")
        for seq in _upstream_ids(upstream_id):
            unsubscribe(seq)


def _quote_callback(
    symbol: str,
    callback: Callable[[dict[str, Any]], None],
) -> Callable[[Any], None]:
    def handle(raw: Any) -> None:
        for quote in normalize_quote_payload(raw, fallback_symbol=symbol):
            callback(quote)

    return handle


def _upstream_ids(upstream_id: Any) -> list[Any]:
    if upstream_id is None:
        return []
    if isinstance(upstream_id, list | tuple | set):
        return list(upstream_id)
    return [upstream_id]
