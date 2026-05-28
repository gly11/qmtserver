from __future__ import annotations

import argparse
import json
from typing import Any, NamedTuple

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings


class ReadonlyEndpoint(NamedTuple):
    name: str
    path: str
    row_key: str | None = None
    needs_account: bool = False


READONLY_ENDPOINTS = [
    ReadonlyEndpoint("account_status", "/v1/trader/account-status", "statuses"),
    ReadonlyEndpoint("asset", "/v1/trader/asset", needs_account=True),
    ReadonlyEndpoint("positions", "/v1/trader/positions", "positions", needs_account=True),
    ReadonlyEndpoint("orders", "/v1/trader/orders", "orders", needs_account=True),
    ReadonlyEndpoint("trades", "/v1/trader/trades", "trades", needs_account=True),
]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_smoke(account_id=args.account_id, account_type=args.account_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if smoke_ok(result) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Readonly smoke for qmtserver trader query endpoints."
    )
    parser.add_argument(
        "--account-id",
        default=None,
        help="optional stock account id; omitted value is loaded from QMT_ACCOUNT_ID",
    )
    parser.add_argument(
        "--account-type",
        default=None,
        help="optional account type; omitted value is loaded from QMT_ACCOUNT_TYPE",
    )
    return parser


def run_smoke(
    *,
    account_id: str | None = None,
    account_type: str | None = None,
) -> dict[str, Any]:
    settings = load_settings(
        auto_connect=True,
        connect_on_startup=True,
        connect_quote=False,
        connect_trader=True,
        require_token=False,
        api_token=None,
    )
    app = create_app(settings, connect_on_startup=True)
    result: dict[str, Any] = {
        "trader_connected": False,
        "quote_connected": None,
        "ready": None,
        "lifecycle": None,
        "last_error": None,
        "endpoints": [],
    }

    with TestClient(app) as client:
        status = client.get("/v1/qmt/status").json()
        result["trader_connected"] = bool(status.get("trader", {}).get("connected"))
        result["quote_connected"] = bool(status.get("quote", {}).get("connected"))
        result["ready"] = status.get("ready")
        result["lifecycle"] = status.get("lifecycle")
        result["last_error"] = _redact_status_error(status.get("last_error"))
        for endpoint in READONLY_ENDPOINTS:
            response = client.get(
                endpoint.path,
                params=endpoint_params(
                    endpoint,
                    account_id=account_id,
                    account_type=account_type,
                ),
            ).json()
            result["endpoints"].append(summarize_response(endpoint.name, response))

    return result


def endpoint_params(
    endpoint: ReadonlyEndpoint,
    *,
    account_id: str | None,
    account_type: str | None,
) -> dict[str, str]:
    if not endpoint.needs_account:
        return {}
    params: dict[str, str] = {}
    if account_id:
        params["account_id"] = account_id
    if account_type:
        params["account_type"] = account_type
    return params


def summarize_response(name: str, response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") or {}
    meta = response.get("meta") or {}
    error = response.get("error") or {}
    summary: dict[str, Any] = {
        "name": name,
        "ok": bool(response.get("ok")),
        "schema": meta.get("schema"),
        "account_id": meta.get("account_id"),
        "account_type": meta.get("account_type"),
        "error_code": error.get("code"),
    }

    row_key = _row_key_for(name)
    if row_key:
        rows = data.get(row_key)
        summary["row_count"] = len(rows) if isinstance(rows, list) else 0
    if name == "asset":
        summary["asset_present"] = isinstance(data.get("asset"), dict)

    return summary


def smoke_ok(result: dict[str, Any]) -> bool:
    if not result.get("trader_connected"):
        return False
    endpoints = result.get("endpoints") or []
    if not endpoints:
        return False
    return all(bool(endpoint.get("ok")) for endpoint in endpoints)


def _row_key_for(name: str) -> str | None:
    for endpoint in READONLY_ENDPOINTS:
        if endpoint.name == name:
            return endpoint.row_key
    return None


def _redact_status_error(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    if "userdata path does not exist:" in text:
        return "userdata path does not exist"
    return text


if __name__ == "__main__":
    raise SystemExit(main())
