from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Protocol


class CoverageRepository(Protocol):
    def list_coverage(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...

    def list_coverage_segments(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class CoveragePlanner:
    def __init__(self, repository: CoverageRepository) -> None:
        self.repository = repository

    def coverage(self, request: dict[str, Any]) -> dict[str, Any]:
        rows = self.repository.list_coverage(request)
        segments = self.repository.list_coverage_segments(request)
        symbols = [str(symbol) for symbol in request.get("symbols", [])]
        gaps_by_symbol = {symbol: _symbol_gaps(symbol, segments, request) for symbol in symbols}
        covered_symbols = {
            symbol
            for symbol in symbols
            if _symbol_has_segments(symbol, segments) and not gaps_by_symbol[symbol]
        }
        missing = [symbol for symbol in symbols if symbol not in covered_symbols]
        gaps = [gap for symbol in symbols for gap in gaps_by_symbol[symbol]]
        return {
            "schema": "market.data.coverage.v1",
            "request": {
                "kind": request.get("kind"),
                "symbols": symbols,
                "period": _period(request),
                "start": request.get("start"),
                "end": request.get("end"),
                "adjust": request.get("adjust", "none"),
            },
            "fully_covered": not missing and bool(symbols),
            "coverage": rows,
            "covered_segments": segments,
            "gaps": gaps,
            "missing_symbols": missing,
        }


def _symbol_has_segments(symbol: str, segments: list[dict[str, Any]]) -> bool:
    return any(str(row.get("symbol")) == symbol for row in segments)


def _symbol_gaps(
    symbol: str,
    segments: list[dict[str, Any]],
    request: dict[str, Any],
) -> list[dict[str, str]]:
    start = request.get("start")
    end = request.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        return (
            []
            if _row_covers_request_for_symbol(symbol, segments, request)
            else [
                {
                    "symbol": symbol,
                    "gap_start": str(start or ""),
                    "gap_end": str(end or ""),
                    "reason": "no_matching_coverage",
                }
            ]
        )
    ranges = [
        (str(row["coverage_start"]), str(row["coverage_end"]))
        for row in segments
        if str(row.get("symbol")) == symbol
        and isinstance(row.get("coverage_start"), str)
        and isinstance(row.get("coverage_end"), str)
        and not (str(row["coverage_end"]) < start or str(row["coverage_start"]) > end)
    ]
    if not ranges:
        return [
            {
                "symbol": symbol,
                "gap_start": start,
                "gap_end": end,
                "reason": "no_matching_coverage",
            }
        ]
    ranges.sort()
    gaps: list[dict[str, str]] = []
    cursor = start
    for coverage_start, coverage_end in ranges:
        if coverage_start > cursor:
            gaps.append(
                {
                    "symbol": symbol,
                    "gap_start": cursor,
                    "gap_end": _previous_value(coverage_start, request),
                    "reason": "segment_gap",
                }
            )
        if coverage_end >= cursor:
            cursor = _next_value(coverage_end, request)
        if cursor > end:
            break
    if cursor <= end:
        gaps.append(
            {
                "symbol": symbol,
                "gap_start": cursor,
                "gap_end": end,
                "reason": "segment_gap",
            }
        )
    return [gap for gap in gaps if gap["gap_start"] <= gap["gap_end"]]


def _row_covers_request_for_symbol(
    symbol: str,
    segments: list[dict[str, Any]],
    request: dict[str, Any],
) -> bool:
    return any(
        str(row.get("symbol")) == symbol and _row_covers_request(row, request) for row in segments
    )


def _row_covers_request(row: dict[str, Any], request: dict[str, Any]) -> bool:
    start = request.get("start")
    end = request.get("end")
    coverage_start = row.get("coverage_start")
    coverage_end = row.get("coverage_end")
    if isinstance(start, str) and isinstance(coverage_start, str) and coverage_start > start:
        return False
    if isinstance(end, str) and isinstance(coverage_end, str) and coverage_end < end:
        return False
    return coverage_start is not None and coverage_end is not None


def _previous_value(value: str, request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        parsed = _date_value(value)
        if parsed is not None:
            return (parsed - timedelta(days=1)).isoformat()
    return value


def _next_value(value: str, request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        parsed = _date_value(value)
        if parsed is not None:
            return (parsed + timedelta(days=1)).isoformat()
    return value


def _date_value(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")
