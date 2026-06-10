from __future__ import annotations

from typing import Any

from qmtserver.data.chunks import progress_from_chunks


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
        "partial": False,
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
        "partial": False,
        "coverage": coverage,
        "files": [],
        "symbol_results": _cached_symbol_results(request, coverage),
        "progress": _cached_progress(request, coverage),
        "next_step": None,
        **_universe_result_metadata(request),
    }


def failed_result(
    request: dict[str, Any],
    chunks: list[dict[str, Any]],
    error: dict[str, str],
) -> dict[str, Any]:
    row_count = sum(int(chunk.get("row_count", 0)) for chunk in chunks)
    file_count = sum(int(chunk.get("file_count", 0)) for chunk in chunks)
    return {
        "schema": "market.data.download.v1",
        "downloaded": any(str(chunk.get("status")) == "succeeded" for chunk in chunks),
        "cached": False,
        "partial": True,
        "symbols": [str(symbol) for symbol in request.get("symbols", [])],
        "kind": request.get("kind"),
        "period": _period(request),
        "storage": "qmtserver_data_lake" if file_count else "miniqmt_cache",
        "file_count": file_count,
        "row_count": row_count,
        "files": [],
        "symbol_results": _chunk_symbol_results(request, chunks, error),
        "progress": progress_from_chunks(chunks),
        "error": error,
        "next_step": "retry_failed_chunks",
        **_universe_result_metadata(request),
    }


def chunked_result(request: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    row_count = sum(int(chunk.get("row_count", 0)) for chunk in chunks)
    file_count = sum(int(chunk.get("file_count", 0)) for chunk in chunks)
    return {
        "schema": "market.data.download.v1",
        "downloaded": bool(chunks),
        "cached": False,
        "partial": False,
        "symbols": [str(symbol) for symbol in request.get("symbols", [])],
        "kind": request.get("kind"),
        "period": _period(request),
        "storage": "qmtserver_data_lake" if file_count else "miniqmt_cache",
        "file_count": file_count,
        "row_count": row_count,
        "files": [],
        "symbol_results": _chunk_symbol_results(request, chunks, {}),
        "progress": progress_from_chunks(chunks),
        "error": None,
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
                "failed": False,
                "row_count": sum(
                    int(file_record.get("row_count", 0)) for file_record in symbol_files
                ),
                "file_count": len(symbol_files),
                "coverage_start": min(starts) if starts else None,
                "coverage_end": max(ends) if ends else None,
                "gaps": [],
                "error": None,
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
                "failed": False,
                "row_count": sum(int(row.get("row_count", 0)) for row in symbol_rows),
                "file_count": sum(int(row.get("file_count", 0)) for row in symbol_rows),
                "coverage_start": min(starts) if starts else None,
                "coverage_end": max(ends) if ends else None,
                "gaps": symbol_gaps,
                "error": None,
            }
        )
    return results


def _cached_progress(request: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in coverage.get("coverage", []) if isinstance(row, dict)]
    requested_symbols = [str(symbol) for symbol in request.get("symbols", [])]
    covered_symbols = {
        str(row["symbol"])
        for row in rows
        if row.get("symbol") is not None
        and (not requested_symbols or str(row["symbol"]) in requested_symbols)
    }
    total_symbols = len(requested_symbols) if requested_symbols else len(covered_symbols)
    return {
        "schema": "market.data.job_progress.v1",
        "total_symbols": total_symbols,
        "finished_symbols": len(covered_symbols),
        "failed_symbols": 0,
        "current_symbol": None,
        "total_chunks": 0,
        "finished_chunks": 0,
        "failed_chunks": 0,
        "running_chunks": 0,
        "queued_chunks": 0,
        "row_count": sum(int(row.get("row_count", 0)) for row in rows),
        "file_count": sum(int(row.get("file_count", 0)) for row in rows),
    }


def _chunk_symbol_results(
    request: dict[str, Any],
    chunks: list[dict[str, Any]],
    job_error: dict[str, str],
) -> list[dict[str, Any]]:
    symbols = [str(symbol) for symbol in request.get("symbols", [])]
    chunks_by_symbol = {
        symbol: [chunk for chunk in chunks if str(chunk.get("symbol")) == symbol]
        for symbol in symbols
    }
    return [
        _chunk_symbol_result(
            symbol,
            chunks_by_symbol.get(symbol, []),
            job_error,
            request,
        )
        for symbol in symbols
    ]


def _chunk_symbol_result(
    symbol: str,
    chunks: list[dict[str, Any]],
    job_error: dict[str, str],
    request: dict[str, Any],
) -> dict[str, Any]:
    failed_chunks = [chunk for chunk in chunks if str(chunk.get("status")) == "failed"]
    succeeded_chunks = [chunk for chunk in chunks if str(chunk.get("status")) == "succeeded"]
    if not chunks:
        failed_chunks = [
            {
                "chunk_start": request.get("start"),
                "chunk_end": request.get("end"),
                "error_code": job_error.get("code"),
                "error_message": job_error.get("message"),
            }
        ]
    starts = [str(chunk["chunk_start"]) for chunk in succeeded_chunks if chunk.get("chunk_start")]
    ends = [str(chunk["chunk_end"]) for chunk in succeeded_chunks if chunk.get("chunk_end")]
    error = _first_chunk_error(failed_chunks, job_error)
    return {
        "symbol": symbol,
        "status": "failed" if failed_chunks else "succeeded",
        "downloaded": bool(succeeded_chunks),
        "cached": False,
        "failed": bool(failed_chunks),
        "row_count": sum(int(chunk.get("row_count", 0)) for chunk in succeeded_chunks),
        "file_count": sum(int(chunk.get("file_count", 0)) for chunk in succeeded_chunks),
        "coverage_start": min(starts) if starts else None,
        "coverage_end": max(ends) if ends else None,
        "gaps": [_failed_chunk_gap(chunk) for chunk in failed_chunks],
        "error": error,
    }


def _failed_chunk_gap(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "gap_start": chunk.get("chunk_start"),
        "gap_end": chunk.get("chunk_end"),
        "reason": "download_failed",
    }


def _first_chunk_error(
    failed_chunks: list[dict[str, Any]],
    job_error: dict[str, str],
) -> dict[str, str] | None:
    if not failed_chunks:
        return None
    first = failed_chunks[0]
    return {
        "code": str(first.get("error_code") or job_error.get("code", "DATA_DOWNLOAD_FAILED")),
        "message": str(
            first.get("error_message") or job_error.get("message", "data download failed")
        ),
    }
