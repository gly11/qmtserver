from __future__ import annotations

from typing import Any, Protocol


class CoverageRepository(Protocol):
    def list_coverage(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class CoveragePlanner:
    def __init__(self, repository: CoverageRepository) -> None:
        self.repository = repository

    def coverage(self, request: dict[str, Any]) -> dict[str, Any]:
        rows = self.repository.list_coverage(request)
        symbols = [str(symbol) for symbol in request.get("symbols", [])]
        covered_symbols = {str(row["symbol"]) for row in rows if _row_covers_request(row, request)}
        missing = [symbol for symbol in symbols if symbol not in covered_symbols]
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
            "missing_symbols": missing,
        }


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


def _period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")
