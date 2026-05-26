from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from qmtserver.data_quality.checks import quality_report
from qmtserver.data_quality.models import QUALITY_SCHEMA


def expected_weekdays(start: str | None, end: str | None) -> list[str]:
    if not start or not end:
        return []
    current = date.fromisoformat(start[:10])
    stop = date.fromisoformat(end[:10])
    values: list[str] = []
    while current <= stop:
        if current.weekday() < 5:
            values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def quality_response(
    rows: list[dict[str, Any]],
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    report = quality_report(rows, expected_dates=expected_weekdays(start, end))
    row_count = len(rows)
    return {
        "ok": True,
        "data": {key: value for key, value in report.items() if key != "schema"},
        "error": None,
        "meta": {
            "schema": QUALITY_SCHEMA,
            "row_count": row_count,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
