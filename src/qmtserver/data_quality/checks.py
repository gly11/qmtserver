from __future__ import annotations

from collections import defaultdict
from typing import Any

from qmtserver.data_quality.models import QUALITY_SCHEMA


def quality_report(
    rows: list[dict[str, Any]],
    *,
    expected_dates: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema": QUALITY_SCHEMA,
        "missing_dates": _missing_dates(rows, expected_dates or []),
        "duplicate_rows": _duplicate_rows(rows),
        "price_anomalies": _price_anomalies(rows),
        "volume_anomalies": _volume_anomalies(rows),
    }


def _missing_dates(
    rows: list[dict[str, Any]],
    expected_dates: list[str],
) -> list[dict[str, str]]:
    if not expected_dates:
        return []
    observed: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        symbol = str(row.get("symbol", ""))
        date = _row_date(row)
        if symbol and date:
            observed[symbol].add(date)
    missing: list[dict[str, str]] = []
    for symbol, dates in observed.items():
        for date in expected_dates:
            if date not in dates:
                missing.append({"symbol": symbol, "date": date})
    return missing


def _duplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    duplicates: list[dict[str, str]] = []
    for row in rows:
        symbol = str(row.get("symbol", ""))
        date = _row_date(row)
        key = (symbol, date)
        if key in seen:
            duplicates.append({"symbol": symbol, "time": date})
        seen.add(key)
    return duplicates


def _price_anomalies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        open_ = _float(row.get("open"))
        high = _float(row.get("high"))
        low = _float(row.get("low"))
        close = _float(row.get("close"))
        if min(open_, high, low, close) <= 0 or high < low or high < max(open_, close):
            result.append(_row_ref(row, "invalid_price"))
    return result


def _volume_anomalies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if _float(row.get("volume")) < 0:
            result.append(_row_ref(row, "invalid_volume"))
    return result


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("timestamp") or "")


def _row_ref(row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"symbol": row.get("symbol"), "time": _row_date(row), "reason": reason}


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)
