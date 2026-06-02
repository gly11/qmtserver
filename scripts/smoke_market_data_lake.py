from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings

READONLY_PATHS = [
    "/v1/health",
    "/v1/market/data/download",
    "/v1/market/data/jobs",
    "/v1/market/data/coverage",
    "/v1/market/data/bars",
    "/v1/market/data/quality",
    "/v1/market/data/exports",
]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_smoke(
        symbols=symbols_from_args(args),
        start=args.start,
        end=args.end,
        timeout_seconds=args.timeout_seconds,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if smoke_ok(result, require_rows=args.require_rows) else 1


def build_parser() -> argparse.ArgumentParser:
    defaults = _default_window()
    parser = argparse.ArgumentParser(
        description="Readonly smoke for qmtserver Market Data Lake download/cache/query/export."
    )
    parser.add_argument("--symbol", default="000001.SZ", help="symbol to download")
    parser.add_argument(
        "--symbols",
        default=None,
        help="comma-separated symbols to download; overrides --symbol",
    )
    parser.add_argument("--start", default=defaults["start"], help="daily start date")
    parser.add_argument("--end", default=defaults["end"], help="daily end date")
    parser.add_argument("--limit", type=int, default=1000, help="local bars query limit")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="data download job wait timeout",
    )
    parser.add_argument(
        "--require-rows",
        action="store_true",
        help="fail unless download, bars, export, and cached download all have rows",
    )
    return parser


def symbols_from_args(args: argparse.Namespace) -> list[str]:
    value = args.symbols if args.symbols else args.symbol
    symbols = [item.strip() for item in value.split(",") if item.strip()]
    return symbols or ["000001.SZ"]


def run_smoke(
    *,
    symbols: list[str],
    start: str,
    end: str,
    timeout_seconds: float,
    limit: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qmtserver-smoke-data-lake-") as tmp:
        root = Path(tmp)
        settings = load_settings(
            auto_connect=True,
            connect_on_startup=True,
            connect_quote=True,
            connect_trader=False,
            require_token=False,
            api_token=None,
            data_dir=root / "market",
            data_db=root / "market" / "db" / "qmtserver.duckdb",
            snapshot_dir=root / "snapshots",
        )
        app = create_app(settings, connect_on_startup=True)
        result: dict[str, Any] = {
            "symbols": symbols,
            "trader_connected": False,
            "health": None,
            "download_job": None,
            "coverage": None,
            "bars": None,
            "quality": None,
            "export": None,
            "cached_download_job": None,
        }
        with TestClient(app) as client:
            result["health"] = summarize_health_response(client.get("/v1/health").json())
            payload = {
                "kind": "daily_bars",
                "symbols": symbols,
                "start": start,
                "end": end,
                "adjust": "none",
                "format": "parquet",
            }
            result["download_job"] = submit_and_wait_data_job(
                client,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
            params = {
                "kind": "daily_bars",
                "symbols": ",".join(symbols),
                "start": start,
                "end": end,
                "adjust": "none",
            }
            result["coverage"] = summarize_coverage_response(
                client.get("/v1/market/data/coverage", params=params).json()
            )
            result["bars"] = summarize_bars_response(
                client.get("/v1/market/data/bars", params={**params, "limit": limit}).json()
            )
            result["quality"] = summarize_quality_response(
                client.get("/v1/market/data/quality", params={**params, "limit": limit}).json()
            )
            result["export"] = create_export_summary(client, {**payload, "format": "csv"})
            result["cached_download_job"] = submit_and_wait_data_job(
                client,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
        return result


def submit_and_wait_data_job(
    client: TestClient,
    *,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    created = client.post("/v1/market/data/download", json=payload).json()
    if not created.get("ok"):
        return summarize_job_response(created)
    job = (created.get("data") or {}).get("job") or {}
    job_id = job.get("job_id")
    latest = created
    deadline = time.monotonic() + timeout_seconds
    while job_id and time.monotonic() < deadline:
        latest = client.get(f"/v1/market/data/jobs/{job_id}").json()
        status = (((latest.get("data") or {}).get("job") or {}).get("status") or "").lower()
        if status in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(0.1)
    return summarize_job_response(latest)


def create_export_summary(client: TestClient, payload: dict[str, Any]) -> dict[str, Any]:
    created = client.post("/v1/market/data/exports", json=payload).json()
    data = created.get("data") or {}
    manifest = data.get("manifest") or {}
    export_id = manifest.get("export_id")
    if export_id:
        client.get(f"/v1/market/data/exports/{export_id}/download")
        client.delete(f"/v1/market/data/exports/{export_id}")
    error = created.get("error") or {}
    return {
        "ok": bool(created.get("ok")),
        "export_id": export_id,
        "row_count": manifest.get("row_count"),
        "source_file_count": manifest.get("source_file_count"),
        "deduplicated_row_count": manifest.get("deduplicated_row_count"),
        "truncated": manifest.get("truncated"),
        "cached": data.get("cached"),
        "error_code": error.get("code"),
    }


def summarize_health_response(response: dict[str, Any]) -> dict[str, Any]:
    return {"ok": bool(response.get("ok")), "error_code": (response.get("error") or {}).get("code")}


def summarize_job_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    job = data.get("job") or {}
    result = job.get("result") or {}
    error = response.get("error") or {}
    return {
        "ok": bool(response.get("ok")) and job.get("status") == "succeeded",
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "downloaded": result.get("downloaded"),
        "cached": result.get("cached", False),
        "row_count": result.get("row_count"),
        "file_count": result.get("file_count"),
        "symbol_results": result.get("symbol_results") or [],
        "error_code": error.get("code") or (job.get("error") or {}).get("code"),
    }


def summarize_coverage_response(response: dict[str, Any]) -> dict[str, Any]:
    coverage = ((response.get("data") or {}).get("coverage")) or {}
    error = response.get("error") or {}
    return {
        "ok": bool(response.get("ok")),
        "fully_covered": coverage.get("fully_covered"),
        "missing_symbols": coverage.get("missing_symbols") or [],
        "gap_count": len(coverage.get("gaps") or []),
        "error_code": error.get("code"),
    }


def summarize_bars_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    error = response.get("error") or {}
    return {
        "ok": bool(response.get("ok")),
        "row_count": data.get("row_count"),
        "total_row_count": data.get("total_row_count"),
        "source_file_count": data.get("source_file_count"),
        "truncated": data.get("truncated"),
        "next_offset": data.get("next_offset"),
        "error_code": error.get("code"),
    }


def summarize_quality_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    error = response.get("error") or {}
    summary = data.get("summary") or {}
    return {
        "ok": bool(response.get("ok")),
        "row_count": summary.get("row_count"),
        "issue_count": summary.get("issue_count"),
        "error_code": error.get("code"),
    }


def smoke_ok(result: dict[str, Any], *, require_rows: bool = False) -> bool:
    if result.get("trader_connected"):
        return False
    required = [
        "health",
        "download_job",
        "coverage",
        "bars",
        "quality",
        "export",
        "cached_download_job",
    ]
    if not all(bool((result.get(name) or {}).get("ok")) for name in required):
        return False
    if not (result.get("coverage") or {}).get("fully_covered"):
        return False
    if not (result.get("cached_download_job") or {}).get("cached"):
        return False
    if require_rows:
        return all(
            int((result.get(name) or {}).get("row_count") or 0) > 0
            for name in ("download_job", "bars", "export", "cached_download_job")
        )
    return True


def _default_window() -> dict[str, str]:
    today = datetime.now().date()
    end = today - timedelta(days=1)
    start = end - timedelta(days=7)
    return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}


if __name__ == "__main__":
    raise SystemExit(main())
