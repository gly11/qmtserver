from __future__ import annotations

import json
from typing import Any

from qmtserver.data.models import DataJobRecord, DataJobStatus


def job_record_from_row(row: tuple[Any, ...]) -> DataJobRecord:
    error = None
    if row[5] or row[6]:
        error = {"code": str(row[5]), "message": str(row[6])}
    return DataJobRecord(
        job_id=str(row[0]),
        job_type=str(row[1]),
        status=DataJobStatus(str(row[2])),
        request=json.loads(str(row[3])),
        result=json.loads(str(row[4])) if row[4] else None,
        error=error,
        created_at=str(row[7]),
        started_at=str(row[8]) if row[8] else None,
        finished_at=str(row[9]) if row[9] else None,
    )


def coverage_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "coverage_id": str(row[0]),
        "kind": str(row[1]),
        "symbol": str(row[2]),
        "period": str(row[3]),
        "adjust": str(row[4]),
        "coverage_start": str(row[5]) if row[5] else None,
        "coverage_end": str(row[6]) if row[6] else None,
        "row_count": int(row[7]),
        "file_count": int(row[8]),
        "updated_at": str(row[9]),
    }


def file_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "file_id": str(row[0]),
        "job_id": str(row[1]) if row[1] else None,
        "kind": str(row[2]),
        "symbol": str(row[3]),
        "period": str(row[4]),
        "adjust": str(row[5]),
        "format": str(row[6]),
        "path": str(row[7]),
        "hash": str(row[8]),
        "row_count": int(row[9]),
        "coverage_start": str(row[10]) if row[10] else None,
        "coverage_end": str(row[11]) if row[11] else None,
        "schema_version": str(row[12]),
        "qmtserver_version": str(row[13]),
        "xtquant_version": str(row[14]) if row[14] else None,
        "created_at": str(row[15]),
    }


def file_matches_request(
    file_record: dict[str, Any],
    request: dict[str, Any],
    *,
    symbols: set[str],
) -> bool:
    if symbols and str(file_record["symbol"]) not in symbols:
        return False
    start = request.get("start")
    end = request.get("end")
    coverage_start = file_record.get("coverage_start")
    coverage_end = file_record.get("coverage_end")
    if isinstance(end, str) and isinstance(coverage_start, str) and coverage_start > end:
        return False
    return not (isinstance(start, str) and isinstance(coverage_end, str) and coverage_end < start)


def coverage_id(record: dict[str, Any]) -> str:
    return ":".join(
        [
            str(record["kind"]),
            str(record["symbol"]),
            str(record["period"]),
            str(record["adjust"]),
        ]
    )


def merge_coverage(
    existing: dict[str, Any] | None,
    file_record: dict[str, Any],
    *,
    coverage_id_value: str,
) -> dict[str, Any]:
    if existing is None:
        return {
            "coverage_id": coverage_id_value,
            "kind": file_record["kind"],
            "symbol": file_record["symbol"],
            "period": file_record["period"],
            "adjust": file_record["adjust"],
            "coverage_start": file_record.get("coverage_start"),
            "coverage_end": file_record.get("coverage_end"),
            "row_count": int(file_record.get("row_count", 0)),
            "file_count": 1,
        }
    starts = [
        item for item in [existing.get("coverage_start"), file_record.get("coverage_start")] if item
    ]
    ends = [
        item for item in [existing.get("coverage_end"), file_record.get("coverage_end")] if item
    ]
    return {
        **existing,
        "coverage_start": min(starts) if starts else None,
        "coverage_end": max(ends) if ends else None,
        "row_count": int(existing.get("row_count", 0)) + int(file_record.get("row_count", 0)),
        "file_count": int(existing.get("file_count", 0)) + 1,
    }


def period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")
