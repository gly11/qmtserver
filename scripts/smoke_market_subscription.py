from __future__ import annotations

import argparse
import json
import threading
import time
from typing import Any

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_smoke(
        symbols=symbols_from_args(args),
        timeout_seconds=args.timeout_seconds,
        require_callback=args.require_callback,
        require_all_symbols=args.require_all_symbols,
        post_stop_listen_seconds=args.post_stop_listen_seconds,
        duration_seconds=args.duration_seconds,
        min_callbacks=args.min_callbacks,
        report_intervals=args.report_intervals,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return (
        0
        if smoke_ok(
            result,
            require_callback=args.require_callback,
            require_all_symbols=args.require_all_symbols,
        )
        else 1
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Readonly smoke for qmtserver market subscriptions."
    )
    parser.add_argument("--symbol", default="000001.SZ", help="symbol to subscribe")
    parser.add_argument(
        "--symbols",
        default=None,
        help="comma-separated symbols to subscribe; overrides --symbol",
    )
    parser.add_argument("--timeout-seconds", type=float, default=8.0, help="event wait timeout")
    parser.add_argument(
        "--require-callback",
        action="store_true",
        help="require a live subscribe_quote callback instead of accepting the initial seed",
    )
    parser.add_argument(
        "--require-all-symbols",
        action="store_true",
        help="require latest quote cache hits for every requested symbol",
    )
    parser.add_argument(
        "--post-stop-listen-seconds",
        type=float,
        default=0.0,
        help="listen briefly after stop and fail if market_quote is still published",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=0.0,
        help="collect quote events for this many seconds instead of stopping after first callback",
    )
    parser.add_argument(
        "--min-callbacks",
        type=int,
        default=0,
        help="minimum live callback count required for a successful smoke",
    )
    parser.add_argument(
        "--report-intervals",
        action="store_true",
        help="include callback interval summary in the smoke result",
    )
    return parser


def symbols_from_args(args: argparse.Namespace) -> list[str]:
    value = args.symbols if args.symbols else args.symbol
    symbols = [item.strip() for item in value.split(",") if item.strip()]
    return symbols or ["000001.SZ"]


def run_smoke(
    *,
    symbols: list[str],
    timeout_seconds: float,
    require_callback: bool,
    require_all_symbols: bool = False,
    post_stop_listen_seconds: float = 0.0,
    duration_seconds: float = 0.0,
    min_callbacks: int = 0,
    report_intervals: bool = False,
) -> dict[str, Any]:
    settings = load_settings(
        auto_connect=True,
        connect_on_startup=True,
        connect_quote=True,
        connect_trader=False,
        require_token=False,
        api_token=None,
        ws_heartbeat_seconds=0.5,
    )
    app = create_app(settings, connect_on_startup=True)
    events: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "symbols": symbols,
        "quote_connected": False,
        "created": None,
        "stopped_status": None,
        "events": events,
        "received_quote": False,
        "received_callback": False,
        "received_quote_symbols": [],
        "callback_symbols": [],
        "latest": None,
        "latest_cache_hit": False,
        "cache_hit_symbols": [],
        "diagnostics": None,
        "diagnostics_ok": False,
        "receiver_error": None,
        "post_stop_events": [],
        "post_stop_market_quote_events": 0,
        "callback_count": 0,
        "callback_report": None,
        "require_callback": require_callback,
        "require_all_symbols": require_all_symbols,
        "post_stop_listen_seconds": post_stop_listen_seconds,
        "duration_seconds": duration_seconds,
        "min_callbacks": min_callbacks,
        "report_intervals": report_intervals,
        "trader_connected": None,
    }

    with TestClient(app) as client:
        status = client.get("/v1/qmt/status").json()
        result["quote_connected"] = bool(status.get("quote", {}).get("connected"))
        result["trader_connected"] = bool(status.get("trader", {}).get("connected"))
        with client.websocket_connect(
            "/v1/ws/events?types=market_subscription,market_quote"
        ) as websocket:
            created = client.post(
                "/v1/market/subscriptions",
                json={"symbols": symbols, "period": "tick"},
            ).json()
            result["created"] = {
                "ok": created.get("ok"),
                "error": created.get("error"),
                "status": (created.get("data") or {}).get("status"),
                "subscription_id": (created.get("data") or {}).get("subscription_id"),
            }

            receiver = threading.Thread(
                target=_receive_events,
                args=(websocket, events, result, require_callback, duration_seconds),
                daemon=True,
            )
            started_at = time.monotonic()
            receiver.start()
            receiver.join(duration_seconds or timeout_seconds)
            elapsed_seconds = round(time.monotonic() - started_at, 3)
            report = callback_report(events, elapsed_seconds=elapsed_seconds)
            result["callback_count"] = report["callback_count"]
            result["callback_symbols"] = list(report["callback_symbols"])
            if report_intervals:
                result["callback_report"] = report

            subscription_id = result["created"]["subscription_id"]
            if subscription_id:
                latest = client.get(f"/v1/market/quotes/latest?symbols={','.join(symbols)}").json()
                result["latest"] = summarize_latest(latest)
                result["latest_cache_hit"] = bool(result["latest"]["quote_count"])
                result["cache_hit_symbols"] = result["latest"]["cache_hit_symbols"]
                diagnostics = client.get(
                    f"/v1/market/subscriptions/{subscription_id}/diagnostics"
                ).json()
                result["diagnostics"] = summarize_diagnostics(diagnostics)
                result["diagnostics_ok"] = bool(
                    (result["diagnostics"]["callback_count"] if require_callback else True)
                    and result["diagnostics"]["last_quote_source"]
                )
                stopped = client.delete(f"/v1/market/subscriptions/{subscription_id}").json()
                result["stopped_status"] = (stopped.get("data") or {}).get("status")
                if post_stop_listen_seconds > 0:
                    _receive_post_stop_events(websocket, result, post_stop_listen_seconds)

    return result


def _receive_events(
    websocket: Any,
    events: list[dict[str, Any]],
    result: dict[str, Any],
    require_callback: bool,
    duration_seconds: float = 0.0,
) -> None:
    try:
        started_at = time.monotonic()
        max_events = 100000 if duration_seconds > 0 else 20
        for _ in range(max_events):
            if duration_seconds > 0 and time.monotonic() - started_at >= duration_seconds:
                return
            event = websocket.receive_json()
            summary = summarize_event(event)
            events.append(summary)
            if summary["type"] != "market_quote":
                continue
            result["received_quote"] = True
            _append_unique(result["received_quote_symbols"], summary.get("symbol"))
            if summary.get("quote_source") == "callback":
                result["received_callback"] = True
                _append_unique(result["callback_symbols"], summary.get("symbol"))
            if duration_seconds > 0:
                continue
            if not require_callback or result["received_callback"]:
                return
    except Exception as exc:
        result["receiver_error"] = f"{type(exc).__name__}: {exc}"


def _receive_post_stop_events(
    websocket: Any,
    result: dict[str, Any],
    timeout_seconds: float,
) -> None:
    post_stop_events: list[dict[str, Any]] = result["post_stop_events"]
    receiver = threading.Thread(
        target=_receive_post_stop_events_until_quote,
        args=(websocket, post_stop_events, result),
        daemon=True,
    )
    receiver.start()
    receiver.join(timeout_seconds)


def _receive_post_stop_events_until_quote(
    websocket: Any,
    events: list[dict[str, Any]],
    result: dict[str, Any],
) -> None:
    try:
        for _ in range(20):
            summary = summarize_event(websocket.receive_json())
            events.append(summary)
            if summary["type"] == "market_quote":
                result["post_stop_market_quote_events"] += 1
                return
    except Exception:
        return


def summarize_event(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") or {}
    meta = event.get("meta") or {}
    return {
        "type": event.get("type"),
        "data_schema": data.get("schema"),
        "symbol": data.get("symbol"),
        "status": data.get("status"),
        "quote_source": meta.get("quote_source"),
        "event_seq": meta.get("event_seq"),
    }


def summarize_latest(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    quotes = data.get("quotes") or []
    return {
        "ok": response.get("ok"),
        "quote_count": len(quotes),
        "cache_hit_symbols": [str(item.get("symbol")) for item in quotes if item.get("symbol")],
        "missing_symbols": data.get("missing_symbols") or [],
    }


def summarize_diagnostics(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    return {
        "ok": response.get("ok"),
        "subscription_id": data.get("subscription_id"),
        "status": data.get("status"),
        "callback_count": data.get("callback_count", 0),
        "initial_quote_count": data.get("initial_quote_count", 0),
        "last_quote_source": data.get("last_quote_source"),
        "last_event_seq": data.get("last_event_seq"),
        "last_initial_quote_at": data.get("last_initial_quote_at"),
        "last_callback_at": data.get("last_callback_at"),
        "seconds_since_last_quote": data.get("seconds_since_last_quote"),
        "seconds_since_last_callback": data.get("seconds_since_last_callback"),
        "is_callback_active": data.get("is_callback_active"),
    }


def callback_report(events: list[dict[str, Any]], *, elapsed_seconds: float) -> dict[str, Any]:
    callback_symbols: dict[str, int] = {}
    callback_event_seq: list[int] = []
    for event in events:
        if event.get("type") != "market_quote" or event.get("quote_source") != "callback":
            continue
        symbol = str(event.get("symbol") or "")
        if symbol:
            callback_symbols[symbol] = callback_symbols.get(symbol, 0) + 1
        event_seq = event.get("event_seq")
        if isinstance(event_seq, int):
            callback_event_seq.append(event_seq)
    return {
        "elapsed_seconds": elapsed_seconds,
        "callback_count": sum(callback_symbols.values()),
        "callback_symbols": callback_symbols,
        "last_callback_event_seq": callback_event_seq[-1] if callback_event_seq else None,
    }


def smoke_ok(
    result: dict[str, Any],
    *,
    require_callback: bool,
    require_all_symbols: bool = False,
) -> bool:
    if not result.get("quote_connected"):
        return False
    created = result.get("created") or {}
    if not created.get("ok"):
        return False
    if result.get("stopped_status") != "stopped":
        return False
    if not result.get("received_quote"):
        return False
    if not result.get("latest_cache_hit"):
        return False
    if not result.get("diagnostics_ok"):
        return False
    if result.get("post_stop_market_quote_events"):
        return False
    if result.get("callback_count", 0) < result.get("min_callbacks", 0):
        return False
    if require_all_symbols:
        expected = set(result.get("symbols") or [])
        actual = set(result.get("cache_hit_symbols") or [])
        if expected - actual:
            return False
    return not (require_callback and not result.get("received_callback"))


def _append_unique(items: list[str], value: Any) -> None:
    if not value:
        return
    item = str(value)
    if item not in items:
        items.append(item)


if __name__ == "__main__":
    raise SystemExit(main())
