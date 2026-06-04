from __future__ import annotations

import json
from typing import Any, Protocol

from qmtserver import __version__
from qmtserver.data.models import DataJobRecord, DataJobStatus, now_iso
from qmtserver.data.records import (
    chunk_from_row,
    coverage_from_row,
    coverage_id,
    file_from_row,
    file_matches_request,
    job_record_from_row,
    merge_coverage,
    period,
)
from qmtserver.miniqmt import check_xtquant_import


class DuckDbBackendProtocol(Protocol):
    database_path: Any

    def connect(self, path: str) -> Any: ...


class DataJobRepository:
    def __init__(self, backend: DuckDbBackendProtocol) -> None:
        self.backend = backend

    def create(self, job_type: str, request: dict[str, Any]) -> DataJobRecord:
        job = DataJobRecord(job_type=job_type, request=request)
        self._execute(
            """
            INSERT INTO data_jobs (
                job_id, job_type, status, request_json, result_json, error_code, error_message,
                created_at, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id,
                job.job_type,
                job.status.value,
                json.dumps(job.request, ensure_ascii=False, sort_keys=True),
                None,
                None,
                None,
                job.created_at,
                None,
                None,
            ),
        )
        return job

    def get(self, job_id: str) -> DataJobRecord | None:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT job_id, job_type, status, request_json, result_json, error_code,
                       error_message, created_at, started_at, finished_at
                FROM data_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return job_record_from_row(row)
        finally:
            connection.close()

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[DataJobRecord]:
        filters = []
        parameters: list[Any] = []
        if status is not None:
            filters.append("status = ?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        parameters.append(max(1, min(limit, 200)))
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                f"""
                SELECT job_id, job_type, status, request_json, result_json, error_code,
                       error_message, created_at, started_at, finished_at
                FROM data_jobs
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                tuple(parameters),
            )
            return [job_record_from_row(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def create_chunks(self, job_id: str, chunks: list[dict[str, Any]]) -> None:
        for index, chunk in enumerate(chunks):
            self._execute(
                """
                INSERT INTO data_job_chunks (
                    chunk_id, job_id, status, symbol, kind, period, adjust, chunk_start, chunk_end,
                    attempts, row_count, file_count, error_code, error_message, gap_reason,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{job_id}:{index:06d}",
                    job_id,
                    chunk.get("status", "queued"),
                    chunk["symbol"],
                    chunk["kind"],
                    chunk["period"],
                    chunk["adjust"],
                    chunk.get("chunk_start"),
                    chunk.get("chunk_end"),
                    int(chunk.get("attempts", 0)),
                    int(chunk.get("row_count", 0)),
                    int(chunk.get("file_count", 0)),
                    chunk.get("error_code"),
                    chunk.get("error_message"),
                    chunk.get("gap_reason"),
                    now_iso(),
                    now_iso(),
                ),
            )

    def list_chunks(self, job_id: str) -> list[dict[str, Any]]:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT chunk_id, job_id, status, symbol, kind, period, adjust, chunk_start,
                       chunk_end, attempts, row_count, file_count, error_code, error_message,
                       gap_reason, created_at, updated_at
                FROM data_job_chunks
                WHERE job_id = ?
                ORDER BY chunk_id
                """,
                (job_id,),
            )
            return [chunk_from_row(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def mark_chunk_running(self, chunk_id: str) -> None:
        self._execute(
            """
            UPDATE data_job_chunks
            SET status = ?, attempts = attempts + 1, updated_at = ?
            WHERE chunk_id = ?
            """,
            ("running", now_iso(), chunk_id),
        )

    def mark_chunk_succeeded(self, chunk_id: str, *, row_count: int, file_count: int) -> None:
        self._execute(
            """
            UPDATE data_job_chunks
            SET status = ?, row_count = ?, file_count = ?, error_code = NULL,
                error_message = NULL, updated_at = ?
            WHERE chunk_id = ?
            """,
            ("succeeded", row_count, file_count, now_iso(), chunk_id),
        )

    def mark_chunk_failed(self, chunk_id: str, error: dict[str, str]) -> None:
        self._execute(
            """
            UPDATE data_job_chunks
            SET status = ?, error_code = ?, error_message = ?, updated_at = ?
            WHERE chunk_id = ?
            """,
            (
                "failed",
                error.get("code", "DATA_DOWNLOAD_FAILED"),
                error.get("message", "data download failed"),
                now_iso(),
                chunk_id,
            ),
        )

    def mark_running(self, job_id: str) -> None:
        self._execute(
            "UPDATE data_jobs SET status = ?, started_at = ? WHERE job_id = ?",
            (DataJobStatus.RUNNING.value, now_iso(), job_id),
        )

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        self._execute(
            """
            UPDATE data_jobs
            SET status = ?, result_json = ?, error_code = NULL, error_message = NULL,
                finished_at = ?
            WHERE job_id = ?
            """,
            (
                DataJobStatus.SUCCEEDED.value,
                json.dumps(result, ensure_ascii=False, sort_keys=True),
                now_iso(),
                job_id,
            ),
        )

    def mark_failed(
        self,
        job_id: str,
        error: dict[str, str],
        *,
        result: dict[str, Any] | None = None,
    ) -> None:
        self._execute(
            """
            UPDATE data_jobs
            SET status = ?, result_json = ?, error_code = ?, error_message = ?, finished_at = ?
            WHERE job_id = ?
            """,
            (
                DataJobStatus.FAILED.value,
                json.dumps(result, ensure_ascii=False, sort_keys=True) if result else None,
                error.get("code", "DATA_DOWNLOAD_FAILED"),
                error.get("message", "data download failed"),
                now_iso(),
                job_id,
            ),
        )

    def record_file(self, file_record: dict[str, Any]) -> None:
        xtquant = check_xtquant_import()
        self._execute(
            """
            INSERT INTO data_files (
                file_id, job_id, kind, symbol, period, adjust, format, path, hash, row_count,
                coverage_start, coverage_end, schema_version, qmtserver_version, xtquant_version,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_record["file_id"],
                file_record.get("job_id"),
                file_record["kind"],
                file_record["symbol"],
                file_record["period"],
                file_record["adjust"],
                file_record["format"],
                file_record["path"],
                file_record["hash"],
                file_record["row_count"],
                file_record.get("coverage_start"),
                file_record.get("coverage_end"),
                file_record.get("schema_version", "market.data.file.v1"),
                __version__,
                xtquant.get("version") if xtquant["ok"] else None,
                now_iso(),
            ),
        )
        self._record_coverage(file_record)

    def clear_file_index(self) -> None:
        self._execute("DELETE FROM data_coverage", ())
        self._execute("DELETE FROM data_files", ())

    def list_coverage(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        symbols = {str(symbol) for symbol in request.get("symbols", [])}
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT coverage_id, kind, symbol, period, adjust, coverage_start, coverage_end,
                       row_count, file_count, updated_at
                FROM data_coverage
                WHERE kind = ? AND period = ? AND adjust = ?
                ORDER BY symbol
                """,
                (
                    request.get("kind"),
                    period(request),
                    request.get("adjust", "none"),
                ),
            )
            coverage = [coverage_from_row(row) for row in cursor.fetchall()]
            if symbols:
                return [row for row in coverage if str(row["symbol"]) in symbols]
            return coverage
        finally:
            connection.close()

    def list_coverage_segments(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "symbol": file_record["symbol"],
                "coverage_start": file_record["coverage_start"],
                "coverage_end": file_record["coverage_end"],
                "row_count": file_record["row_count"],
                "file_count": 1,
                "file_id": file_record["file_id"],
            }
            for file_record in self.list_files(request)
        ]

    def list_all_files(self) -> list[dict[str, Any]]:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT file_id, job_id, kind, symbol, period, adjust, format, path, hash,
                       row_count, coverage_start, coverage_end, schema_version,
                       qmtserver_version, xtquant_version, created_at
                FROM data_files
                ORDER BY symbol, coverage_start
                """
            )
            return [file_from_row(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def list_files(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        symbols = {str(symbol) for symbol in request.get("symbols", [])}
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT file_id, job_id, kind, symbol, period, adjust, format, path, hash,
                       row_count, coverage_start, coverage_end, schema_version,
                       qmtserver_version, xtquant_version, created_at
                FROM data_files
                WHERE kind = ? AND period = ? AND adjust = ?
                ORDER BY symbol, coverage_start
                """,
                (
                    request.get("kind"),
                    period(request),
                    request.get("adjust", "none"),
                ),
            )
            files = [file_from_row(row) for row in cursor.fetchall()]
            return [
                file_record
                for file_record in files
                if file_matches_request(file_record, request, symbols=symbols)
            ]
        finally:
            connection.close()

    def _execute(self, sql: str, parameters: tuple[Any, ...]) -> Any:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            return connection.execute(sql, parameters)
        finally:
            connection.close()

    def _record_coverage(self, file_record: dict[str, Any]) -> None:
        coverage_id_value = coverage_id(file_record)
        existing = self._get_coverage(coverage_id_value)
        merged = merge_coverage(existing, file_record, coverage_id_value=coverage_id_value)
        self._execute("DELETE FROM data_coverage WHERE coverage_id = ?", (coverage_id_value,))
        self._execute(
            """
            INSERT INTO data_coverage (
                coverage_id, kind, symbol, period, adjust, coverage_start, coverage_end,
                row_count, file_count, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                merged["coverage_id"],
                merged["kind"],
                merged["symbol"],
                merged["period"],
                merged["adjust"],
                merged["coverage_start"],
                merged["coverage_end"],
                merged["row_count"],
                merged["file_count"],
                now_iso(),
            ),
        )

    def _get_coverage(self, coverage_id: str) -> dict[str, Any] | None:
        connection = self.backend.connect(str(self.backend.database_path))
        try:
            cursor = connection.execute(
                """
                SELECT coverage_id, kind, symbol, period, adjust, coverage_start, coverage_end,
                       row_count, file_count, updated_at
                FROM data_coverage
                WHERE coverage_id = ?
                """,
                (coverage_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return coverage_from_row(row)
        finally:
            connection.close()
