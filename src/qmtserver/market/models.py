from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

BAR_SCHEMA = "market.bars.v1"
CAPABILITIES_SCHEMA = "market.capabilities.v1"
SUPPORTED_PERIODS = ("1m", "5m", "15m", "30m", "60m")
ADJUST_MODES = ("none", "front", "back", "front_ratio", "back_ratio")

MarketKind = Literal["daily", "intraday"]


class DailyBar(TypedDict):
    date: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int | float
    amount: float
    meta: dict[str, Any]


class IntradayBar(TypedDict):
    timestamp: str
    symbol: str
    period: str
    open: float
    high: float
    low: float
    close: float
    volume: int | float
    amount: float
    meta: dict[str, Any]


@dataclass(frozen=True)
class MarketRequest:
    symbols: list[str]
    start: str | None
    end: str | None
    adjust: str = "none"
    period: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "symbols": self.symbols,
            "start": self.start,
            "end": self.end,
            "adjust": self.adjust,
        }
        if self.period is not None:
            data["period"] = self.period
        return data
