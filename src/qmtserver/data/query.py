from __future__ import annotations

from typing import Any, Protocol, cast


class DataFileRepository(Protocol):
    def list_files(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class DuckDbBackend(Protocol):
    database_path: Any

    def connect(self, path: str) -> Any: ...


class BarFileReader(Protocol):
    def read_bars(
        self,
        files: list[dict[str, Any]],
        request: dict[str, Any],
    ) -> list[dict[str, Any]]: ...


class AggregatingBarFileReader(BarFileReader, Protocol):
    def query_bars(
        self,
        files: list[dict[str, Any]],
        request: dict[str, Any],
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]: ...


class LocalBarQuery:
    def __init__(self, repository: DataFileRepository, *, reader: BarFileReader) -> None:
        self.repository = repository
        self.reader = reader

    def query_bars(self, request: dict[str, Any]) -> dict[str, Any]:
        files = self.repository.list_files(request)
        limit = _limit(request)
        offset = _offset(request)
        if hasattr(self.reader, "query_bars"):
            aggregating_reader = cast(AggregatingBarFileReader, self.reader)
            return aggregating_reader.query_bars(files, request, limit=limit, offset=offset)
        rows = self.reader.read_bars(files, request) if files else []
        sorted_rows = sorted(rows, key=_sort_key)
        unique_rows = _deduplicate_rows(sorted_rows)
        page = unique_rows[offset : offset + limit]
        truncated = offset + len(page) < len(unique_rows)
        response: dict[str, Any] = {
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
        response["query_profile"] = _query_profile(
            engine="python",
            mode="fallback",
            files=files,
            limit=limit,
            offset=offset,
            raw_row_count=len(rows),
            total_row_count=len(unique_rows),
            returned_row_count=len(page),
        )
        response["recommendations"] = _recommendations(response, limit=limit)
        return response


class DuckDbParquetBarReader:
    def __init__(self, backend: DuckDbBackend) -> None:
        self.backend = backend

    def read_bars(
        self,
        files: list[dict[str, Any]],
        request: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self.query_bars(files, request, limit=10000, offset=0)["bars"]

    def query_bars(
        self,
        files: list[dict[str, Any]],
        request: dict[str, Any],
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        if not files:
            response: dict[str, Any] = _empty_response(request, limit=limit, offset=offset)
            response["query_profile"] = _query_profile(
                engine="duckdb",
                mode="empty",
                files=[],
                limit=limit,
                offset=offset,
                raw_row_count=0,
                total_row_count=0,
                returned_row_count=0,
            )
            response["recommendations"] = []
            return response
        paths = [str(file_record["path"]) for file_record in files]
        count_sql, count_parameters = _count_sql(paths, request)
        page_sql, page_parameters = _page_sql(paths, request, limit=limit, offset=offset)
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            count_cursor = connection.execute(count_sql, count_parameters)
            count_row = count_cursor.fetchone() or (0, 0)
            raw_row_count = int(count_row[0])
            total_row_count = int(count_row[1])
            page_cursor = connection.execute(page_sql, page_parameters)
            columns = [str(item[0]) for item in page_cursor.description]
            rows = [dict(zip(columns, row, strict=False)) for row in page_cursor.fetchall()]
        finally:
            connection.close()
        truncated = offset + len(rows) < total_row_count
        response: dict[str, Any] = {
            "schema": "market.data.bars.v1",
            "request": _request_meta(request),
            "bars": rows,
            "row_count": len(rows),
            "total_row_count": total_row_count,
            "source_file_count": len(files),
            "deduplicated_row_count": raw_row_count - total_row_count,
            "truncated": truncated,
            "next_offset": offset + len(rows) if truncated else None,
        }
        response["query_profile"] = _query_profile(
            engine="duckdb",
            mode="multi_file" if len(files) > 1 else "single_file",
            files=files,
            limit=limit,
            offset=offset,
            raw_row_count=raw_row_count,
            total_row_count=total_row_count,
            returned_row_count=len(rows),
        )
        response["recommendations"] = _recommendations(response, limit=limit)
        return response

    def _read_file(self, path: str, request: dict[str, Any]) -> list[dict[str, Any]]:
        sql, parameters = _read_sql(path, request)
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(sql, parameters)
            columns = [str(item[0]) for item in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        finally:
            connection.close()


def _empty_response(request: dict[str, Any], *, limit: int, offset: int) -> dict[str, Any]:
    return {
        "schema": "market.data.bars.v1",
        "request": _request_meta({**request, "limit": limit, "offset": offset}),
        "bars": [],
        "row_count": 0,
        "total_row_count": 0,
        "source_file_count": 0,
        "deduplicated_row_count": 0,
        "truncated": False,
        "next_offset": None,
    }


def _read_sql(path: str, request: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    source_sql, parameters = _source_sql([path], request)
    return f"SELECT * FROM ({source_sql})", parameters


def _count_sql(paths: list[str], request: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    source_sql, parameters = _source_sql(paths, request)
    partition = _dedupe_partition(request)
    time_column = _time_column(request)
    sql = f"""
    WITH source AS ({source_sql}),
    ranked AS (
        SELECT
            ROW_NUMBER() OVER (
                PARTITION BY {partition}
                ORDER BY symbol, {time_column}
            ) AS __rn
        FROM source
    )
    SELECT
        (SELECT COUNT(*) FROM source) AS raw_row_count,
        (SELECT COUNT(*) FROM ranked WHERE __rn = 1) AS total_row_count
    """
    return sql, parameters


def _page_sql(
    paths: list[str],
    request: dict[str, Any],
    *,
    limit: int,
    offset: int,
) -> tuple[str, tuple[Any, ...]]:
    source_sql, parameters = _source_sql(paths, request)
    partition = _dedupe_partition(request)
    time_column = _time_column(request)
    sql = f"""
    WITH source AS ({source_sql}),
    ranked AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY {partition}
                ORDER BY symbol, {time_column}
            ) AS __rn
        FROM source
    )
    SELECT * EXCLUDE (__rn)
    FROM ranked
    WHERE __rn = 1
    ORDER BY symbol, {time_column}
    LIMIT ? OFFSET ?
    """
    return sql, (*parameters, limit, offset)


def _source_sql(paths: list[str], request: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    time_column = "date" if request.get("kind") == "daily_bars" else "timestamp"
    filters = ["1 = 1"]
    parameters: list[Any] = list(paths)
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
    sql = f"SELECT * FROM {_read_parquet_call(len(paths))} WHERE {' AND '.join(filters)}"
    return sql, tuple(parameters)


def _read_parquet_call(path_count: int) -> str:
    placeholders = ", ".join("?" for _ in range(path_count))
    return f"read_parquet([{placeholders}], union_by_name = true)"


def _time_column(request: dict[str, Any]) -> str:
    return "date" if request.get("kind") == "daily_bars" else "timestamp"


def _dedupe_partition(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "symbol, date"
    return "symbol, period, timestamp"


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


def _query_profile(
    *,
    engine: str,
    mode: str,
    files: list[dict[str, Any]],
    limit: int,
    offset: int,
    raw_row_count: int,
    total_row_count: int,
    returned_row_count: int,
) -> dict[str, Any]:
    return {
        "schema": "market.data.query_profile.v1",
        "engine": engine,
        "mode": mode,
        "source_file_count": len(files),
        "limit": limit,
        "offset": offset,
        "raw_row_count": raw_row_count,
        "total_row_count": total_row_count,
        "returned_row_count": returned_row_count,
    }


def _recommendations(response: dict[str, Any], *, limit: int) -> list[str]:
    recommendations = []
    if response.get("truncated"):
        recommendations.append("Use next_offset to request the next page.")
    if int(response.get("total_row_count", 0)) > limit:
        recommendations.append("Use POST /v1/market/data/exports for large result exports.")
    return recommendations
