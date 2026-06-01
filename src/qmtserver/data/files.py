from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from qmtserver.errors import QmtDataBackendUnavailableError


class ParquetBarWriter:
    def __init__(
        self,
        data_dir: Path,
        *,
        import_module: Callable[[str], object] = importlib.import_module,
    ) -> None:
        self.data_dir = data_dir
        self.import_module = import_module

    def write_bars(
        self,
        request: dict[str, Any],
        bars: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        pyarrow = self._module("pyarrow")
        parquet = self._module("pyarrow.parquet")
        files = []
        for symbol, rows in sorted(_group_by_symbol(bars).items()):
            data_hash = _rows_hash(rows)
            coverage_start, coverage_end = _coverage(str(request.get("kind")), rows)
            path = self._path(
                request=request,
                symbol=symbol,
                coverage_start=coverage_start,
                coverage_end=coverage_end,
                data_hash=data_hash,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            table = pyarrow.Table.from_pylist(rows)
            parquet.write_table(table, path)
            files.append(
                {
                    "file_id": data_hash.removeprefix("sha256:")[:16],
                    "kind": request.get("kind"),
                    "symbol": symbol,
                    "period": _period(request),
                    "adjust": request.get("adjust", "none"),
                    "format": "parquet",
                    "path": str(path),
                    "hash": data_hash,
                    "row_count": len(rows),
                    "coverage_start": coverage_start,
                    "coverage_end": coverage_end,
                }
            )
        return files

    def _module(self, name: str) -> Any:
        try:
            return self.import_module(name)
        except ModuleNotFoundError as exc:
            raise QmtDataBackendUnavailableError(
                f"Data lake Parquet writer requires qmtserver[data]; missing: {name}"
            ) from exc

    def _path(
        self,
        *,
        request: dict[str, Any],
        symbol: str,
        coverage_start: str | None,
        coverage_end: str | None,
        data_hash: str,
    ) -> Path:
        start = _path_part(coverage_start or str(request.get("start") or "unknown"))
        end = _path_part(coverage_end or str(request.get("end") or "unknown"))
        suffix = data_hash.removeprefix("sha256:")[:12]
        return (
            self.data_dir
            / "raw"
            / "bars"
            / f"kind={request.get('kind')}"
            / f"period={_period(request)}"
            / f"adjust={request.get('adjust', 'none')}"
            / f"symbol={symbol}"
            / f"part-{start}-{end}-{suffix}.parquet"
        )


def _group_by_symbol(bars: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for bar in bars:
        symbol = bar.get("symbol")
        if not symbol:
            continue
        grouped.setdefault(str(symbol), []).append(bar)
    return grouped


def _coverage(kind: str, rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    key = "date" if kind == "daily_bars" else "timestamp"
    values = sorted(str(row[key]) for row in rows if row.get(key))
    if not values:
        return None, None
    return values[0], values[-1]


def _period(request: dict[str, Any]) -> str:
    if request.get("kind") == "daily_bars":
        return "1d"
    return str(request.get("period") or "unknown")


def _path_part(value: str) -> str:
    return value.replace(":", "").replace("+", "").replace("/", "-").replace("\\", "-")


def _rows_hash(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
