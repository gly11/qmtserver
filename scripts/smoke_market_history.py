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
    "/v1/market/bars/daily",
    "/v1/market/bars/intraday",
    "/v1/market/bars/daily/quality",
    "/v1/snapshots",
    "/v1/jobs/history-download",
]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_smoke(
        symbols=symbols_from_args(args),
        start=args.start,
        end=args.end,
        intraday_start=args.intraday_start,
        intraday_end=args.intraday_end,
        period=args.period,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if smoke_ok(result, require_rows=args.require_rows) else 1


def build_parser() -> argparse.ArgumentParser:
    defaults = _default_window()
    parser = argparse.ArgumentParser(
        description="Readonly smoke for qmtserver market history, snapshots, and jobs."
    )
    parser.add_argument("--symbol", default="000001.SZ", help="symbol to query")
    parser.add_argument(
        "--symbols",
        default=None,
        help="comma-separated symbols to query; overrides --symbol",
    )
    parser.add_argument("--start", default=defaults["start"], help="daily start date")
    parser.add_argument("--end", default=defaults["end"], help="daily end date")
    parser.add_argument(
        "--intraday-start",
        default=defaults["intraday_start"],
        help="intraday start datetime, ISO format with timezone",
    )
    parser.add_argument(
        "--intraday-end",
        default=defaults["intraday_end"],
        help="intraday end datetime, ISO format with timezone",
    )
    parser.add_argument("--period", default="1m", help="intraday period")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="history download job wait timeout",
    )
    parser.add_argument(
        "--require-rows",
        action="store_true",
        help="fail unless daily, intraday, snapshot, and job summaries all have rows",
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
    intraday_start: str,
    intraday_end: str,
    period: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qmtserver-smoke-history-") as tmp:
        settings = load_settings(
            auto_connect=True,
            connect_on_startup=True,
            connect_quote=True,
            connect_trader=False,
            require_token=False,
            api_token=None,
            snapshot_dir=Path(tmp),
        )
        app = create_app(settings, connect_on_startup=True)
        result: dict[str, Any] = {
            "symbols": symbols,
            "quote_connected": False,
            "trader_connected": None,
            "daily": None,
            "intraday": None,
            "quality": None,
            "snapshot": None,
            "job": None,
            "intraday_job": None,
        }

        with TestClient(app) as client:
            status = client.get("/v1/qmt/status").json()
            result["quote_connected"] = bool(status.get("quote", {}).get("connected"))
            result["trader_connected"] = bool(status.get("trader", {}).get("connected"))
            symbol_text = ",".join(symbols)
            daily_request = {
                "symbols": symbol_text,
                "start": start,
                "end": end,
                "adjust": "none",
            }
            intraday_request = {
                "symbols": symbol_text,
                "period": period,
                "start": intraday_start,
                "end": intraday_end,
                "adjust": "none",
            }
            result["job"] = run_history_job(
                client,
                payload={
                    "kind": "daily_bars",
                    "symbols": symbols,
                    "start": start,
                    "end": end,
                    "adjust": "none",
                    "format": "csv",
                },
                timeout_seconds=timeout_seconds,
            )
            result["intraday_job"] = run_history_job(
                client,
                payload={
                    "kind": "intraday_bars",
                    "symbols": symbols,
                    "period": period,
                    "start": intraday_start,
                    "end": intraday_end,
                    "adjust": "none",
                    "format": "csv",
                },
                timeout_seconds=timeout_seconds,
            )
            daily = client.get("/v1/market/bars/daily", params=daily_request).json()
            result["daily"] = summarize_bars_response("daily", daily)
            intraday = client.get("/v1/market/bars/intraday", params=intraday_request).json()
            result["intraday"] = summarize_bars_response("intraday", intraday)
            quality = client.get("/v1/market/bars/daily/quality", params=daily_request).json()
            result["quality"] = summarize_quality_response(quality)
            snapshot = client.post(
                "/v1/snapshots",
                json={
                    "kind": "daily_bars",
                    "symbols": symbols,
                    "start": start,
                    "end": end,
                    "adjust": "none",
                    "format": "csv",
                },
            ).json()
            result["snapshot"] = summarize_snapshot_response(snapshot)
        return result


def run_history_job(
    client: TestClient,
    *,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    created = client.post("/v1/jobs/history-download", json=payload).json()
    if not created.get("ok"):
        return summarize_job_response(created)
    job = (created.get("data") or {}).get("job") or {}
    job_id = job.get("job_id")
    deadline = time.monotonic() + timeout_seconds
    latest = created
    while job_id and time.monotonic() < deadline:
        latest = client.get(f"/v1/jobs/{job_id}").json()
        status = (((latest.get("data") or {}).get("job") or {}).get("status") or "").lower()
        if status in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(0.1)
    return summarize_job_response(latest)


def summarize_bars_response(name: str, response: dict[str, Any]) -> dict[str, Any]:
    meta = response.get("meta") or {}
    request = meta.get("request") or {}
    error = response.get("error") or {}
    return {
        "name": name,
        "ok": bool(response.get("ok")),
        "schema": meta.get("schema"),
        "row_count": meta.get("row_count", 0),
        "symbols": request.get("symbols") or [],
        "error_code": error.get("code"),
    }


def summarize_quality_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    error = response.get("error") or {}
    summary = data.get("summary") or {}
    return {
        "ok": bool(response.get("ok")),
        "schema": data.get("schema"),
        "row_count": summary.get("row_count"),
        "issue_count": summary.get("issue_count"),
        "error_code": error.get("code"),
    }


def summarize_snapshot_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    manifest = data.get("manifest") or {}
    error = response.get("error") or {}
    return {
        "ok": bool(response.get("ok")),
        "snapshot_id": manifest.get("snapshot_id"),
        "row_count": manifest.get("row_count"),
        "symbol_count": manifest.get("symbol_count"),
        "format": manifest.get("format"),
        "cached": data.get("cached"),
        "error_code": error.get("code"),
    }


def summarize_job_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    job = data.get("job") or {}
    error = response.get("error") or {}
    result = job.get("result") or {}
    return {
        "ok": bool(response.get("ok")) and job.get("status") == "succeeded",
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "snapshot_id": result.get("snapshot_id"),
        "row_count": result.get("row_count"),
        "error_code": error.get("code") or (job.get("error") or {}).get("code"),
    }


def smoke_ok(result: dict[str, Any], *, require_rows: bool = False) -> bool:
    if not result.get("quote_connected"):
        return False
    required_scopes = ["daily", "intraday", "quality", "snapshot", "job"]
    if result.get("intraday_job") is not None:
        required_scopes.append("intraday_job")
    scopes_ok = all(bool((result.get(name) or {}).get("ok")) for name in required_scopes)
    if not scopes_ok:
        return False
    if require_rows:
        return all(
            int((result.get(name) or {}).get("row_count") or 0) > 0
            for name in ("daily", "intraday", "snapshot", "job", "intraday_job")
        )
    return True


def _default_window() -> dict[str, str]:
    today = datetime.now().date()
    start = today - timedelta(days=7)
    return {
        "start": start.strftime("%Y-%m-%d"),
        "end": today.strftime("%Y-%m-%d"),
        "intraday_start": f"{today.strftime('%Y-%m-%d')}T09:30:00+08:00",
        "intraday_end": f"{today.strftime('%Y-%m-%d')}T15:00:00+08:00",
    }


if __name__ == "__main__":
    raise SystemExit(main())
