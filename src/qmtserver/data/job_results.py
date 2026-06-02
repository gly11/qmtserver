from __future__ import annotations

from typing import Any


def download_result(request: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    symbols = request.get("symbols")
    row_count = sum(int(file_record.get("row_count", 0)) for file_record in files)
    requested_symbols = [str(symbol) for symbol in symbols] if isinstance(symbols, list) else []
    return {
        "schema": "market.data.download.v1",
        "downloaded": True,
        "symbols": requested_symbols,
        "kind": request.get("kind"),
        "period": _period(request),
        "storage": "qmtserver_data_lake" if files else "miniqmt_cache",
        "file_count": len(files),
        "row_count": row_count,
        "files": files,
        "symbol_results": _download_symbol_results(requested_symbols, files),
        "next_step": None if files else "parquet_writer_pending",
        **_universe_result_metadata(request),
    }


def cached_result(request: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    rows = coverage.get("coverage", [])
    row_count = sum(int(row.get("row_count", 0)) for row in rows if isinstance(row, dict))
    file_count = sum(int(row.get("file_count", 0)) for row in rows if isinstance(row, dict))
    return {
        "schema": "market.data.download.v1",
        "downloaded": False,
        "cached": True,
        "symbols": [str(symbol) for symbol in request.get("symbols", [])],
        "kind": request.get("kind"),
        "period": _period(request),
        "storage": "qmtserver_data_lake",
        "file_count": file_count,
        "row_count": row_count,
        "coverage": coverage,
        "files": [],
        "symbol_results": _cached_symbol_results(request, coverage),
        "next_step": None,
        **_universe_result_metadata(request),
    }


def _period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")


def _universe_result_metadata(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "universe": request.get("universe"),
        "exchange": request.get("exchange"),
        "symbol_count": int(request.get("symbol_count", len(request.get("symbols", [])))),
        "universe_hash": request.get("universe_hash"),
    }


def _download_symbol_results(
    symbols: list[str],
    files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for symbol in symbols:
        symbol_files = [
            file_record for file_record in files if str(file_record.get("symbol")) == symbol
        ]
        starts = [
            str(file_record["coverage_start"])
            for file_record in symbol_files
            if file_record.get("coverage_start")
        ]
        ends = [
            str(file_record["coverage_end"])
            for file_record in symbol_files
            if file_record.get("coverage_end")
        ]
        results.append(
            {
                "symbol": symbol,
                "status": "succeeded",
                "downloaded": True,
                "cached": False,
                "row_count": sum(
                    int(file_record.get("row_count", 0)) for file_record in symbol_files
                ),
                "file_count": len(symbol_files),
                "coverage_start": min(starts) if starts else None,
                "coverage_end": max(ends) if ends else None,
                "gaps": [],
            }
        )
    return results


def _cached_symbol_results(
    request: dict[str, Any], coverage: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = coverage.get("coverage", [])
    gaps = coverage.get("gaps", [])
    results = []
    for symbol in [str(symbol) for symbol in request.get("symbols", [])]:
        symbol_rows = [
            row for row in rows if isinstance(row, dict) and str(row.get("symbol")) == symbol
        ]
        symbol_gaps = [
            gap for gap in gaps if isinstance(gap, dict) and str(gap.get("symbol")) == symbol
        ]
        starts = [str(row["coverage_start"]) for row in symbol_rows if row.get("coverage_start")]
        ends = [str(row["coverage_end"]) for row in symbol_rows if row.get("coverage_end")]
        results.append(
            {
                "symbol": symbol,
                "status": "cached" if symbol_rows and not symbol_gaps else "missing",
                "downloaded": False,
                "cached": bool(symbol_rows and not symbol_gaps),
                "row_count": sum(int(row.get("row_count", 0)) for row in symbol_rows),
                "file_count": sum(int(row.get("file_count", 0)) for row in symbol_rows),
                "coverage_start": min(starts) if starts else None,
                "coverage_end": max(ends) if ends else None,
                "gaps": symbol_gaps,
            }
        )
    return results
