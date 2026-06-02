from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def plan_download_chunks(request: dict[str, Any]) -> list[dict[str, Any]]:
    symbols = [str(symbol) for symbol in request.get("symbols", [])]
    if not symbols:
        return []
    ranges = _date_ranges(
        start=request.get("start"),
        end=request.get("end"),
        chunk_days=_chunk_days(request),
    )
    return [
        _chunk(request, symbol=symbol, chunk_start=chunk_start, chunk_end=chunk_end)
        for symbol in symbols
        for chunk_start, chunk_end in ranges
    ]


def _date_ranges(
    *,
    start: object,
    end: object,
    chunk_days: int,
) -> list[tuple[str | None, str | None]]:
    if not isinstance(start, str) or not isinstance(end, str):
        return [(None, None)]
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if start_date is None or end_date is None or start_date > end_date:
        return [(start, end)]
    ranges = []
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end_date)
        ranges.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return ranges


def _chunk(
    request: dict[str, Any],
    *,
    symbol: str,
    chunk_start: str | None,
    chunk_end: str | None,
) -> dict[str, Any]:
    return {
        "status": "queued",
        "symbol": symbol,
        "kind": request.get("kind"),
        "period": _period(request),
        "adjust": request.get("adjust", "none"),
        "chunk_start": chunk_start,
        "chunk_end": chunk_end,
        "attempts": 0,
        "row_count": 0,
        "file_count": 0,
        "error_code": None,
        "error_message": None,
    }


def _chunk_days(request: dict[str, Any]) -> int:
    value = request.get("chunk_days", 31)
    if not isinstance(value, int):
        return 31
    return max(1, min(value, 366))


def _period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
