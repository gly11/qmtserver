from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from qmtserver.market.models import DailyBar, IntradayBar
from qmtserver.market.subscription_models import QUOTE_SCHEMA

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

_QUOTE_KEYS = {
    "time",
    "timestamp",
    "datetime",
    "symbol",
    "stock_code",
    "code",
    "lastPrice",
    "last_price",
    "price",
    "volume",
    "vol",
    "amount",
}


def normalize_daily_bars(raw: Any) -> list[DailyBar]:
    bars: list[DailyBar] = []
    for record in _records(raw):
        symbol = _text(_first(record, "symbol", "stock_code", "code"))
        bar: DailyBar = {
            "date": _date_text(_first(record, "date", "time", "timestamp", "datetime")),
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


def normalize_quote_payload(
    raw: Any,
    *,
    fallback_symbol: str | None = None,
) -> list[dict[str, Any]]:
    quotes: list[dict[str, Any]] = []
    for record in _quote_records(raw, fallback_symbol=fallback_symbol):
        symbol = _text(_first(record, "symbol", "stock_code", "code"))
        if not symbol and fallback_symbol:
            symbol = fallback_symbol
        quote = {
            "schema": QUOTE_SCHEMA,
            "symbol": symbol,
            "time": _text(_first(record, "time", "timestamp", "datetime")),
            "last_price": _float(_first(record, "last_price", "lastPrice", "price")),
            "volume": _number(_first(record, "volume", "vol")),
            "amount": _float(record.get("amount")),
            "extra": {key: value for key, value in record.items() if key not in _QUOTE_KEYS},
        }
        quotes.append(quote)
    return quotes


def _records(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if hasattr(raw, "to_dict"):
        converted = _table_records(raw)
        return _records(converted)
    if isinstance(raw, Mapping):
        return _records_from_mapping(raw)
    if isinstance(raw, list | tuple):
        result: list[dict[str, Any]] = []
        for item in raw:
            result.extend(_records(item))
        return result
    return []


def _table_records(raw: Any) -> list[dict[str, Any]]:
    converted = raw.to_dict("records")
    if not isinstance(converted, list) or not hasattr(raw, "index"):
        return converted
    index_values = list(raw.index)
    if len(index_values) != len(converted):
        return converted
    records: list[dict[str, Any]] = []
    for index, record in zip(index_values, converted, strict=True):
        if isinstance(record, Mapping):
            item = dict(record)
            item.setdefault("date", index)
            records.append(item)
    return records


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


def _quote_records(raw: Any, *, fallback_symbol: str | None) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, Mapping):
        text_keys = {str(key) for key in raw}
        if text_keys & _QUOTE_KEYS:
            record = {str(key): value for key, value in raw.items()}
            if fallback_symbol:
                record.setdefault("symbol", fallback_symbol)
            return [record]
        result: list[dict[str, Any]] = []
        for symbol, value in raw.items():
            for record in _quote_records(value, fallback_symbol=str(symbol)):
                result.append(record)
        return result
    if isinstance(raw, list | tuple):
        result: list[dict[str, Any]] = []
        for item in raw:
            result.extend(_quote_records(item, fallback_symbol=fallback_symbol))
        return result
    return []


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


def _date_text(value: Any) -> str:
    text = _text(value).strip()
    if not text:
        return ""
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    if text.isdigit() and len(text) == 8:
        try:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8])).isoformat()
        except ValueError:
            return text
    if text.isdigit():
        converted = _epoch_date_text(int(text), len(text))
        return converted or text
    return text


def _epoch_date_text(value: int, text_length: int) -> str | None:
    try:
        if text_length >= 19:
            seconds = value / 1_000_000_000
        elif text_length >= 16:
            seconds = value / 1_000_000
        elif text_length >= 13:
            seconds = value / 1_000
        else:
            seconds = value
        return datetime.fromtimestamp(seconds, UTC).date().isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _meta(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in _FIELD_KEYS}
