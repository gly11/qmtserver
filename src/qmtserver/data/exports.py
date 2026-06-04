from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from qmtserver import __version__
from qmtserver.errors import QmtInvalidSnapshotRequestError, QmtSnapshotNotFoundError
from qmtserver.miniqmt import check_xtquant_import
from qmtserver.snapshots.manifest import request_hash
from qmtserver.snapshots.registry import SnapshotRegistry
from qmtserver.snapshots.writers import write_csv


class BarQuery(Protocol):
    def query_bars(self, request: dict[str, Any]) -> dict[str, Any]: ...


class DataExportService:
    def __init__(self, query: BarQuery, *, root: Path) -> None:
        self.query = query
        self.registry = SnapshotRegistry(root)

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            canonical = _canonical_request(request)
            req_hash = request_hash(canonical)
            export_id = f"export-{req_hash.removeprefix('sha256:')[:16]}"
            existing = self.registry.get(export_id)
            if existing is not None:
                return _success(existing, cached=True)

            query_response = self.query.query_bars({**canonical, "limit": _export_limit(request)})
            bars = query_response["bars"]
            data_path = self.registry.data_path(export_id, canonical["format"])
            data_hash = write_csv(data_path, bars, kind=canonical["kind"])
            manifest = _manifest(
                export_id=export_id,
                request=canonical,
                request_hash_value=req_hash,
                data_hash=data_hash,
                data_path=data_path,
                bars=bars,
                query_response=query_response,
            )
            self.registry.save({"snapshot_id": export_id, **manifest})
            return _success(manifest, cached=False)
        except QmtInvalidSnapshotRequestError as exc:
            return {
                "ok": False,
                "data": None,
                "error": {"code": exc.code, "message": str(exc)},
                "meta": {},
            }

    def manifest(self, export_id: str) -> dict[str, Any]:
        manifest = self.registry.get(export_id)
        if manifest is None:
            raise QmtSnapshotNotFoundError(f"data export not found: {export_id}")
        return _strip_snapshot_id(manifest)

    def list_exports(self) -> list[dict[str, Any]]:
        return [_strip_snapshot_id(manifest) for manifest in self.registry.list_manifests()]

    def download_path(self, export_id: str) -> Path:
        manifest = self.manifest(export_id)
        path = self.registry.data_path(export_id, str(manifest["format"]))
        if not path.exists():
            raise QmtSnapshotNotFoundError(f"data export file not found: {export_id}")
        return path

    def delete(self, export_id: str) -> bool:
        manifest = self.registry.get(export_id)
        if manifest is None:
            return False
        format_name = str(manifest.get("format", "csv"))
        data_path = self.registry.data_path(export_id, format_name)
        manifest_path = self.registry.root / f"{export_id}.manifest.json"
        deleted = False
        for path in (data_path, manifest_path):
            if path.exists():
                path.unlink()
                deleted = True
        return deleted


def _canonical_request(request: dict[str, Any]) -> dict[str, Any]:
    symbols = request.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise QmtInvalidSnapshotRequestError("symbols must include at least one symbol")
    kind = request.get("kind", "daily_bars")
    if kind not in {"daily_bars", "intraday_bars"}:
        raise QmtInvalidSnapshotRequestError(f"unsupported data export kind: {kind}")
    format_name = request.get("format", "csv")
    if format_name != "csv":
        raise QmtInvalidSnapshotRequestError(f"unsupported data export format: {format_name}")
    canonical = {
        "kind": kind,
        "symbols": [str(symbol).strip() for symbol in symbols if str(symbol).strip()],
        "start": request.get("start"),
        "end": request.get("end"),
        "adjust": request.get("adjust", "none"),
        "format": format_name,
    }
    if kind == "intraday_bars":
        period = request.get("period")
        if not period:
            raise QmtInvalidSnapshotRequestError("intraday data export requires period")
        canonical["period"] = period
    return canonical


def _manifest(
    *,
    export_id: str,
    request: dict[str, Any],
    request_hash_value: str,
    data_hash: str,
    data_path: Path,
    bars: list[dict[str, Any]],
    query_response: dict[str, Any],
) -> dict[str, Any]:
    xtquant = check_xtquant_import()
    coverage_start, coverage_end = _coverage(request["kind"], bars)
    return {
        "export_id": export_id,
        "request_hash": request_hash_value,
        "schema": "market.data.export.v1",
        "format": request["format"],
        "request": request,
        "hash": data_hash,
        "download": _download_metadata(
            filename=data_path.name,
            format_name=request["format"],
            data_hash=data_hash,
            data_path=data_path,
        ),
        "row_count": len(bars),
        "source_file_count": int(query_response.get("source_file_count", 0)),
        "deduplicated_row_count": int(query_response.get("deduplicated_row_count", 0)),
        "truncated": bool(query_response.get("truncated", False)),
        "symbol_count": len(request["symbols"]),
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "generated_at": datetime.now(UTC).isoformat(),
        "qmtserver_version": __version__,
        "xtquant_version": xtquant.get("version") if xtquant["ok"] else None,
    }


def _download_metadata(
    *,
    filename: str,
    format_name: str,
    data_hash: str,
    data_path: Path,
) -> dict[str, Any]:
    return {
        "filename": filename,
        "format": format_name,
        "content_length": data_path.stat().st_size,
        "hash": data_hash,
        "etag": f'"{data_hash}"',
    }


def _coverage(kind: str, bars: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    key = "date" if kind == "daily_bars" else "timestamp"
    values = sorted(str(bar[key]) for bar in bars if bar.get(key))
    if not values:
        return None, None
    return values[0], values[-1]


def _export_limit(request: dict[str, Any]) -> int:
    value = request.get("limit", 10000)
    return value if isinstance(value, int) else 10000


def _strip_snapshot_id(manifest: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key != "snapshot_id"}


def _success(manifest: dict[str, Any], *, cached: bool) -> dict[str, Any]:
    return {"ok": True, "data": {"manifest": manifest, "cached": cached}, "error": None, "meta": {}}
