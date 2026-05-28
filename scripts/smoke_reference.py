from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_smoke(
        symbols=symbols_from_args(args),
        universe_name=args.universe,
        start=args.start,
        end=args.end,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if smoke_ok(result) else 1


def build_parser() -> argparse.ArgumentParser:
    defaults = _default_window()
    parser = argparse.ArgumentParser(
        description="Readonly smoke for qmtserver reference endpoints."
    )
    parser.add_argument("--symbol", default="000001.SZ", help="instrument symbol")
    parser.add_argument(
        "--symbols",
        default=None,
        help="comma-separated symbols to query; overrides --symbol",
    )
    parser.add_argument("--universe", default="all_a", help="reference universe name")
    parser.add_argument("--start", default=defaults["start"], help="calendar start date")
    parser.add_argument("--end", default=defaults["end"], help="calendar end date")
    return parser


def symbols_from_args(args: argparse.Namespace) -> list[str]:
    value = args.symbols if args.symbols else args.symbol
    symbols = [item.strip() for item in value.split(",") if item.strip()]
    return symbols or ["000001.SZ"]


def run_smoke(
    *,
    symbols: list[str],
    universe_name: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    settings = load_settings(
        auto_connect=True,
        connect_on_startup=True,
        connect_quote=True,
        connect_trader=False,
        require_token=False,
        api_token=None,
    )
    app = create_app(settings, connect_on_startup=True)
    result: dict[str, Any] = {
        "symbols": symbols,
        "quote_connected": False,
        "trader_connected": None,
        "calendar": None,
        "universe": None,
        "instruments": None,
    }

    with TestClient(app) as client:
        status = client.get("/v1/qmt/status").json()
        result["quote_connected"] = bool(status.get("quote", {}).get("connected"))
        result["trader_connected"] = bool(status.get("trader", {}).get("connected"))
        calendar = client.get(
            "/v1/reference/calendar",
            params={"start": start, "end": end},
        ).json()
        result["calendar"] = summarize_calendar_response(calendar)
        universe = client.get(
            "/v1/reference/universe",
            params={"name": universe_name},
        ).json()
        result["universe"] = summarize_universe_response(universe)
        instruments = client.get(
            "/v1/reference/instruments",
            params={"symbols": ",".join(symbols)},
        ).json()
        result["instruments"] = summarize_instruments_response(instruments)

    return result


def summarize_calendar_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    error = response.get("error") or {}
    dates = data.get("dates") or []
    return {
        "ok": bool(response.get("ok")),
        "schema": (response.get("meta") or {}).get("schema"),
        "date_count": len(dates) if isinstance(dates, list) else 0,
        "source": data.get("source"),
        "error_code": error.get("code"),
    }


def summarize_universe_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    error = response.get("error") or {}
    symbols = data.get("symbols") or []
    return {
        "ok": bool(response.get("ok")),
        "schema": (response.get("meta") or {}).get("schema"),
        "name": data.get("name"),
        "symbol_count": len(symbols) if isinstance(symbols, list) else 0,
        "error_code": error.get("code"),
    }


def summarize_instruments_response(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    error = response.get("error") or {}
    instruments = data.get("instruments") or []
    observed_fields: set[str] = set()
    if isinstance(instruments, list):
        for item in instruments:
            if isinstance(item, dict):
                observed_fields.update(str(key) for key in item)
    return {
        "ok": bool(response.get("ok")),
        "schema": (response.get("meta") or {}).get("schema"),
        "instrument_count": len(instruments) if isinstance(instruments, list) else 0,
        "observed_fields": sorted(observed_fields),
        "error_code": error.get("code"),
    }


def smoke_ok(result: dict[str, Any]) -> bool:
    if not result.get("quote_connected"):
        return False
    calendar = result.get("calendar") or {}
    universe = result.get("universe") or {}
    instruments = result.get("instruments") or {}
    return bool(
        calendar.get("ok")
        and int(calendar.get("date_count") or 0) > 0
        and universe.get("ok")
        and int(universe.get("symbol_count") or 0) > 0
        and instruments.get("ok")
        and int(instruments.get("instrument_count") or 0) > 0
    )


def _default_window() -> dict[str, str]:
    today = datetime.now().date()
    start = today - timedelta(days=7)
    return {
        "start": start.strftime("%Y-%m-%d"),
        "end": today.strftime("%Y-%m-%d"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
