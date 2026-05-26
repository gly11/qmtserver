from __future__ import annotations

from typing import Any

from qmtserver.rpc.serializers import to_jsonable

TRADER_READONLY_SCHEMA = "trader.readonly.v1"

ASSET_FIELDS = (
    "account_id",
    "cash",
    "frozen_cash",
    "market_value",
    "total_asset",
    "fetch_balance",
)
POSITION_FIELDS = (
    "account_id",
    "stock_code",
    "volume",
    "can_use_volume",
    "open_price",
    "market_value",
)
ORDER_FIELDS = (
    "account_id",
    "order_id",
    "stock_code",
    "order_type",
    "order_volume",
    "price_type",
    "price",
    "order_status",
    "status_msg",
    "strategy_name",
    "order_remark",
)
TRADE_FIELDS = (
    "account_id",
    "trade_id",
    "stock_code",
    "order_id",
    "traded_volume",
    "traded_price",
    "traded_amount",
    "traded_time",
)
ACCOUNT_STATUS_FIELDS = ("account_id", "account_type", "status")


def normalize_account_status(value: Any) -> dict[str, Any]:
    return _normalize(value, ACCOUNT_STATUS_FIELDS)


def normalize_asset(value: Any) -> dict[str, Any]:
    return _normalize(value, ASSET_FIELDS)


def normalize_position(value: Any) -> dict[str, Any]:
    return _normalize(value, POSITION_FIELDS)


def normalize_order(value: Any) -> dict[str, Any]:
    return _normalize(value, ORDER_FIELDS)


def normalize_trade(value: Any) -> dict[str, Any]:
    return _normalize(value, TRADE_FIELDS)


def _normalize(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    raw = _public_mapping(value)
    result = {field: to_jsonable(raw.get(field)) for field in fields}
    result["extra"] = {
        key: to_jsonable(item)
        for key, item in raw.items()
        if key not in fields and not key.startswith("_")
    }
    return result


def _public_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items() if not str(key).startswith("_")}
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return {}
