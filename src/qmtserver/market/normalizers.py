from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from qmtserver.market.models import DailyBar, IntradayBar

_FIELD_KEYS = {
    "date",
    "time",
    "timestamp",
    "datetime",
    "symbol",
    "stock_code",
    "code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vol",
    "amount",
}


def normalize_daily_bars(raw: Any) -> list[DailyBar]:
    bars: list[DailyBar] = []
    for record in _records(raw):
        symbol = _text(_first(record, "symbol", "stock_code", "code"))
        bar: DailyBar = {
            "date": _text(_first(record, "date", "time", "timestamp", "datetime")),
            "symbol": symbol,
            "open": _float(record.get("open")),
            "high": _float(record.get("high")),
            "low": _float(record.get("low")),
            "close": _float(record.get("close")),
            "volume": _number(_first(record, "volume", "vol")),
            "amount": _float(record.get("amount")),
            "meta": _meta(record),
        }
        bars.append(bar)
    return bars


def normalize_intraday_bars(raw: Any, *, period: str) -> list[IntradayBar]:
    bars: list[IntradayBar] = []
    for record in _records(raw):
        symbol = _text(_first(record, "symbol", "stock_code", "code"))
        bar: IntradayBar = {
            "timestamp": _text(_first(record, "timestamp", "time", "datetime", "date")),
            "symbol": symbol,
            "period": period,
            "open": _float(record.get("open")),
            "high": _float(record.get("high")),
            "low": _float(record.get("low")),
            "close": _float(record.get("close")),
            "volume": _number(_first(record, "volume", "vol")),
            "amount": _float(record.get("amount")),
            "meta": _meta(record),
        }
        bars.append(bar)
    return bars


def _records(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if hasattr(raw, "to_dict"):
        converted = raw.to_dict("records")
        return _records(converted)
    if isinstance(raw, Mapping):
        return _records_from_mapping(raw)
    if isinstance(raw, list | tuple):
        result: list[dict[str, Any]] = []
        for item in raw:
            result.extend(_records(item))
        return result
    return []


def _records_from_mapping(raw: Mapping[Any, Any]) -> list[dict[str, Any]]:
    text_keys = {str(key) for key in raw}
    if text_keys & _FIELD_KEYS:
        if _is_columnar(raw):
            return _columnar_records(raw)
        return [{str(key): value for key, value in raw.items()}]

    result: list[dict[str, Any]] = []
    for symbol, value in raw.items():
        for record in _records(value):
            record.setdefault("symbol", str(symbol))
            result.append(record)
    return result


def _is_columnar(raw: Mapping[Any, Any]) -> bool:
    values = list(raw.values())
    return bool(values) and all(_is_sequence(value) for value in values)


def _columnar_records(raw: Mapping[Any, Any]) -> list[dict[str, Any]]:
    columns = {str(key): list(value) for key, value in raw.items() if _is_sequence(value)}
    if not columns:
        return []
    row_count = min(len(value) for value in columns.values())
    return [{key: value[index] for key, value in columns.items()} for index in range(row_count)]


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, str | bytes | Mapping)


def _first(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _number(value: Any) -> int | float:
    if isinstance(value, int | float):
        return value
    if value is None:
        return 0
    number = float(value)
    return int(number) if number.is_integer() else number


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _meta(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in _FIELD_KEYS}
