from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qmtserver import __version__
from qmtserver.errors import QmtInvalidSnapshotRequestError, QmtSnapshotNotFoundError
from qmtserver.market import MarketService
from qmtserver.market.models import BAR_SCHEMA
from qmtserver.miniqmt import check_xtquant_import
from qmtserver.snapshots.manifest import request_hash
from qmtserver.snapshots.registry import SnapshotRegistry
from qmtserver.snapshots.writers import write_csv


class SnapshotService:
    def __init__(self, qmt_service: Any, *, root: Path) -> None:
        self.qmt_service = qmt_service
        self.registry = SnapshotRegistry(root)

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            canonical = self._canonical_request(request)
            req_hash = request_hash(canonical)
            existing = self.registry.find_by_request_hash(req_hash)
            if existing is not None:
                return self._success(existing, cached=True)

            market = MarketService(self.qmt_service)
            symbols = ",".join(canonical["symbols"])
            if canonical["kind"] == "daily_bars":
                response = market.daily_bars(
                    symbols=symbols,
                    start=canonical["start"],
                    end=canonical["end"],
                    adjust=canonical["adjust"],
                )
            else:
                response = market.intraday_bars(
                    symbols=symbols,
                    period=canonical["period"],
                    start=canonical["start"],
                    end=canonical["end"],
                    adjust=canonical["adjust"],
                )
            if not response["ok"]:
                return response

            bars = response["data"]["bars"]
            snapshot_id = f"{canonical['kind']}-{req_hash.removeprefix('sha256:')[:16]}"
            data_path = self.registry.data_path(snapshot_id, canonical["format"])
            data_hash = write_csv(data_path, bars)
            manifest = self._manifest(
                snapshot_id=snapshot_id,
                request=canonical,
                request_hash_value=req_hash,
                data_hash=data_hash,
                bars=bars,
            )
            self.registry.save(manifest)
            return self._success(manifest, cached=False)
        except QmtInvalidSnapshotRequestError as exc:
            return self._error(exc.code, str(exc))

    def list_snapshots(self) -> dict[str, Any]:
        return {
            "ok": True,
            "data": {"snapshots": self.registry.list_manifests()},
            "error": None,
            "meta": {},
        }

    def manifest(self, snapshot_id: str) -> dict[str, Any]:
        manifest = self.registry.get(snapshot_id)
        if manifest is None:
            raise QmtSnapshotNotFoundError(f"snapshot not found: {snapshot_id}")
        return {"ok": True, "data": {"manifest": manifest}, "error": None, "meta": {}}

    def download_path(self, snapshot_id: str) -> Path:
        manifest = self.registry.get(snapshot_id)
        if manifest is None:
            raise QmtSnapshotNotFoundError(f"snapshot not found: {snapshot_id}")
        path = self.registry.data_path(snapshot_id, str(manifest["format"]))
        if not path.exists():
            raise QmtSnapshotNotFoundError(f"snapshot data not found: {snapshot_id}")
        return path

    def _canonical_request(self, request: dict[str, Any]) -> dict[str, Any]:
        symbols = request.get("symbols")
        if not isinstance(symbols, list) or not symbols:
            raise QmtInvalidSnapshotRequestError("symbols must include at least one symbol")
        kind = request.get("kind")
        if kind not in {"daily_bars", "intraday_bars"}:
            raise QmtInvalidSnapshotRequestError(f"unsupported snapshot kind: {kind}")
        format_name = request.get("format", "csv")
        if format_name != "csv":
            raise QmtInvalidSnapshotRequestError(f"unsupported snapshot format: {format_name}")
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
                raise QmtInvalidSnapshotRequestError("intraday snapshot requires period")
            canonical["period"] = period
        return canonical

    def _manifest(
        self,
        *,
        snapshot_id: str,
        request: dict[str, Any],
        request_hash_value: str,
        data_hash: str,
        bars: list[dict[str, Any]],
    ) -> dict[str, Any]:
        xtquant = check_xtquant_import()
        coverage = self._coverage(request["kind"], bars)
        return {
            "snapshot_id": snapshot_id,
            "request_hash": request_hash_value,
            "schema": BAR_SCHEMA,
            "format": request["format"],
            "request": request,
            "hash": data_hash,
            "row_count": len(bars),
            "symbol_count": len(request["symbols"]),
            "coverage_start": coverage[0],
            "coverage_end": coverage[1],
            "generated_at": datetime.now(UTC).isoformat(),
            "qmtserver_version": __version__,
            "xtquant_version": xtquant.get("version") if xtquant["ok"] else None,
        }

    def _coverage(self, kind: str, bars: list[dict[str, Any]]) -> tuple[str | None, str | None]:
        key = "date" if kind == "daily_bars" else "timestamp"
        values = sorted(str(bar[key]) for bar in bars if bar.get(key))
        if not values:
            return None, None
        return values[0], values[-1]

    def _success(self, manifest: dict[str, Any], *, cached: bool) -> dict[str, Any]:
        return {
            "ok": True,
            "data": {"manifest": manifest, "cached": cached},
            "error": None,
            "meta": {},
        }

    def _error(self, code: str, message: str) -> dict[str, Any]:
        return {"ok": False, "data": None, "error": {"code": code, "message": message}, "meta": {}}
