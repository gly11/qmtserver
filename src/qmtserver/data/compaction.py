from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol


class CompactionEngine(Protocol):
    def compact(self, group: dict[str, Any], output_path: Path) -> dict[str, Any]: ...


def plan_compaction_groups(
    files: list[dict[str, Any]],
    *,
    data_dir: Path,
    min_files: int = 2,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for file_record in files:
        key = (
            str(file_record.get("kind") or "daily_bars"),
            str(file_record.get("symbol") or "unknown"),
            str(file_record.get("period") or "unknown"),
            str(file_record.get("adjust") or "none"),
        )
        grouped.setdefault(key, []).append(file_record)
    groups = []
    for (kind, symbol, period, adjust), records in sorted(grouped.items()):
        if len(records) < max(2, min_files):
            continue
        starts = [
            str(record["coverage_start"]) for record in records if record.get("coverage_start")
        ]
        ends = [str(record["coverage_end"]) for record in records if record.get("coverage_end")]
        group = {
            "kind": kind,
            "symbol": symbol,
            "period": period,
            "adjust": adjust,
            "source_file_count": len(records),
            "source_files": [_source_file(record) for record in records],
            "row_count": sum(int(record.get("row_count", 0)) for record in records),
            "coverage_start": min(starts) if starts else None,
            "coverage_end": max(ends) if ends else None,
        }
        group["output_path"] = str(_output_path(data_dir, group))
        groups.append(group)
    return groups


class ParquetCompactionEngine:
    def compact(self, group: dict[str, Any], output_path: Path) -> dict[str, Any]:
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = []
        for source in group["source_files"]:
            rows.extend(pq.read_table(str(source["path"])).to_pylist())
        rows = _deduplicate_rows(rows, kind=str(group["kind"]), period=str(group["period"]))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows), output_path)
        return {
            "file_id": _file_id(rows, group),
            "kind": group["kind"],
            "symbol": group["symbol"],
            "period": group["period"],
            "adjust": group["adjust"],
            "format": "parquet",
            "path": str(output_path),
            "hash": "sha256:" + _rows_digest(rows),
            "row_count": len(rows),
            "coverage_start": _coverage_start(rows, str(group["kind"])),
            "coverage_end": _coverage_end(rows, str(group["kind"])),
        }


def _source_file(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_id": record.get("file_id"),
        "path": str(record.get("path")),
        "row_count": int(record.get("row_count", 0)),
        "coverage_start": record.get("coverage_start"),
        "coverage_end": record.get("coverage_end"),
    }


def _output_path(data_dir: Path, group: dict[str, Any]) -> Path:
    key = "|".join(
        [
            str(group["kind"]),
            str(group["symbol"]),
            str(group["period"]),
            str(group["adjust"]),
            str(group.get("coverage_start") or ""),
            str(group.get("coverage_end") or ""),
        ]
    )
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return (
        data_dir
        / "raw"
        / "bars"
        / f"kind={group['kind']}"
        / f"period={group['period']}"
        / f"adjust={group['adjust']}"
        / f"symbol={group['symbol']}"
        / f"compact-{digest}.parquet"
    )


def _deduplicate_rows(
    rows: list[dict[str, Any]],
    *,
    kind: str,
    period: str,
) -> list[dict[str, Any]]:
    key_field = "date" if kind == "daily_bars" else "timestamp"
    deduped = {}
    for row in rows:
        key = (str(row.get("symbol")), period, str(row.get(key_field)))
        deduped[key] = row
    return [deduped[key] for key in sorted(deduped)]


def _file_id(rows: list[dict[str, Any]], group: dict[str, Any]) -> str:
    if rows:
        return _rows_digest(rows)[:16]
    key = f"{group['kind']}:{group['symbol']}:{group['period']}:{group['adjust']}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _rows_digest(rows: list[dict[str, Any]]) -> str:
    payload = repr(sorted(rows, key=lambda row: repr(row))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _coverage_start(rows: list[dict[str, Any]], kind: str) -> str | None:
    values = _coverage_values(rows, kind)
    return values[0] if values else None


def _coverage_end(rows: list[dict[str, Any]], kind: str) -> str | None:
    values = _coverage_values(rows, kind)
    return values[-1] if values else None


def _coverage_values(rows: list[dict[str, Any]], kind: str) -> list[str]:
    key = "date" if kind == "daily_bars" else "timestamp"
    return sorted(str(row[key]) for row in rows if row.get(key))
