from __future__ import annotations

from typing import Any, Protocol

from qmtserver.data.backend import DuckDbDataBackend


class DataFileRepository(Protocol):
    def list_files(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class BarFileReader(Protocol):
    def read_bars(
        self,
        files: list[dict[str, Any]],
        request: dict[str, Any],
    ) -> list[dict[str, Any]]: ...


class LocalBarQuery:
    def __init__(self, repository: DataFileRepository, *, reader: BarFileReader) -> None:
        self.repository = repository
        self.reader = reader

    def query_bars(self, request: dict[str, Any]) -> dict[str, Any]:
        files = self.repository.list_files(request)
        limit = _limit(request)
        offset = _offset(request)
        rows = self.reader.read_bars(files, request) if files else []
        sorted_rows = sorted(rows, key=_sort_key)
        unique_rows = _deduplicate_rows(sorted_rows)
        page = unique_rows[offset : offset + limit]
        truncated = offset + len(page) < len(unique_rows)
        return {
            "schema": "market.data.bars.v1",
            "request": _request_meta(request),
            "bars": page,
            "row_count": len(page),
            "total_row_count": len(unique_rows),
            "source_file_count": len(files),
            "deduplicated_row_count": len(rows) - len(unique_rows),
            "truncated": truncated,
            "next_offset": offset + len(page) if truncated else None,
        }


class DuckDbParquetBarReader:
    def __init__(self, backend: DuckDbDataBackend) -> None:
        self.backend = backend

    def read_bars(
        self,
        files: list[dict[str, Any]],
        request: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for file_record in files:
            rows.extend(self._read_file(str(file_record["path"]), request))
        return sorted(rows, key=_sort_key)

    def _read_file(self, path: str, request: dict[str, Any]) -> list[dict[str, Any]]:
        sql, parameters = _read_sql(path, request)
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(sql, parameters)
            columns = [str(item[0]) for item in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        finally:
            connection.close()


def _read_sql(path: str, request: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    time_column = "date" if request.get("kind") == "daily_bars" else "timestamp"
    filters = ["1 = 1"]
    parameters: list[Any] = [path]
    symbols = [str(symbol) for symbol in request.get("symbols", [])]
    if symbols:
        placeholders = ", ".join("?" for _ in symbols)
        filters.append(f"symbol IN ({placeholders})")
        parameters.extend(symbols)
    if request.get("start"):
        filters.append(f"{time_column} >= ?")
        parameters.append(request["start"])
    if request.get("end"):
        filters.append(f"{time_column} <= ?")
        parameters.append(request["end"])
    sql = f"SELECT * FROM read_parquet(?) WHERE {' AND '.join(filters)}"
    return sql, tuple(parameters)


def _limit(request: dict[str, Any]) -> int:
    value = request.get("limit", 1000)
    if not isinstance(value, int):
        return 1000
    return max(1, min(value, 10000))


def _offset(request: dict[str, Any]) -> int:
    value = request.get("offset", 0)
    if not isinstance(value, int):
        return 0
    return max(0, value)


def _request_meta(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": request.get("kind"),
        "symbols": [str(symbol) for symbol in request.get("symbols", [])],
        "period": _period(request),
        "start": request.get("start"),
        "end": request.get("end"),
        "adjust": request.get("adjust", "none"),
        "limit": _limit(request),
        "offset": _offset(request),
    }


def _period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")


def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("symbol", "")),
        str(row.get("date") or row.get("timestamp") or ""),
    )


def _deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for row in rows:
        key = (
            str(row.get("symbol", "")),
            str(row.get("period", "")),
            str(row.get("date") or row.get("timestamp") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique
