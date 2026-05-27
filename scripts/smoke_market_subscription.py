from __future__ import annotations

import argparse
import json
import threading
from typing import Any

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_smoke(
        symbol=args.symbol,
        timeout_seconds=args.timeout_seconds,
        require_callback=args.require_callback,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if smoke_ok(result, require_callback=args.require_callback) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Readonly smoke for qmtserver market subscriptions."
    )
    parser.add_argument("--symbol", default="000001.SZ", help="symbol to subscribe")
    parser.add_argument("--timeout-seconds", type=float, default=8.0, help="event wait timeout")
    parser.add_argument(
        "--require-callback",
        action="store_true",
        help="require a live subscribe_quote callback instead of accepting the initial seed",
    )
    return parser


def run_smoke(
    *,
    symbol: str,
    timeout_seconds: float,
    require_callback: bool,
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
        "symbol": symbol,
        "quote_connected": False,
        "created": None,
        "stopped_status": None,
        "events": events,
        "received_quote": False,
        "received_callback": False,
        "require_callback": require_callback,
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
                json={"symbols": [symbol], "period": "tick"},
            ).json()
            result["created"] = {
                "ok": created.get("ok"),
                "error": created.get("error"),
                "status": (created.get("data") or {}).get("status"),
                "subscription_id": (created.get("data") or {}).get("subscription_id"),
            }

            receiver = threading.Thread(
                target=_receive_events,
                args=(websocket, events, result, require_callback),
                daemon=True,
            )
            receiver.start()
            receiver.join(timeout_seconds)

            subscription_id = result["created"]["subscription_id"]
            if subscription_id:
                stopped = client.delete(f"/v1/market/subscriptions/{subscription_id}").json()
                result["stopped_status"] = (stopped.get("data") or {}).get("status")

    return result


def _receive_events(
    websocket: Any,
    events: list[dict[str, Any]],
    result: dict[str, Any],
    require_callback: bool,
) -> None:
    for _ in range(20):
        event = websocket.receive_json()
        summary = summarize_event(event)
        events.append(summary)
        if summary["type"] != "market_quote":
            continue
        result["received_quote"] = True
        if summary.get("quote_source") == "callback":
            result["received_callback"] = True
        if not require_callback or result["received_callback"]:
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
    }


def smoke_ok(result: dict[str, Any], *, require_callback: bool) -> bool:
    if not result.get("quote_connected"):
        return False
    created = result.get("created") or {}
    if not created.get("ok"):
        return False
    if result.get("stopped_status") != "stopped":
        return False
    if not result.get("received_quote"):
        return False
    return not (require_callback and not result.get("received_callback"))


if __name__ == "__main__":
    raise SystemExit(main())
