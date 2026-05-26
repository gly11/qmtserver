from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from qmtserver.snapshots.manifest import content_hash

CSV_COLUMNS = ("date", "symbol", "open", "high", "low", "close", "volume", "amount", "meta")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
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
