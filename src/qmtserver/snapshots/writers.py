from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from qmtserver.snapshots.manifest import content_hash

DAILY_CSV_COLUMNS = ("date", "symbol", "open", "high", "low", "close", "volume", "amount", "meta")
INTRADAY_CSV_COLUMNS = (
    "timestamp",
    "symbol",
    "period",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "meta",
)


def write_csv(path: Path, rows: list[dict[str, Any]], *, kind: str = "daily_bars") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_columns_for_kind(kind), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            prepared = dict(row)
            prepared["meta"] = json.dumps(
                prepared.get("meta", {}),
                ensure_ascii=False,
                sort_keys=True,
            )
            writer.writerow(prepared)
    return content_hash(path.read_bytes())


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> str:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
    return content_hash(path.read_bytes())


def _columns_for_kind(kind: str) -> tuple[str, ...]:
    if kind == "intraday_bars":
        return INTRADAY_CSV_COLUMNS
    return DAILY_CSV_COLUMNS
