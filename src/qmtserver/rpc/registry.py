from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RpcMethodLevel = Literal["readonly", "trading", "admin", "transparent"]


@dataclass(frozen=True)
class RpcMethodSpec:
    target: str
    method: str
    level: RpcMethodLevel
    enabled: bool = True


READONLY_METHODS: dict[str, set[str]] = {
    "xtdata": {
        "get_full_tick",
        "get_market_data",
        "get_market_data_ex",
        "get_instrument_detail",
        "get_stock_list_in_sector",
    },
    "trader": {
        "query_account_infos",
        "query_account_status",
        "query_stock_asset",
        "query_stock_positions",
        "query_stock_orders",
        "query_stock_trades",
    },
}

TRADING_METHODS: dict[str, set[str]] = {
    "trader": {
        "order_stock",
        "order_stock_async",
        "cancel_order_stock",
        "cancel_order_stock_async",
    },
}

RPC_METHODS: dict[tuple[str, str], RpcMethodSpec] = {}
for _target, _methods in READONLY_METHODS.items():
    for _method in _methods:
        RPC_METHODS[(_target, _method)] = RpcMethodSpec(_target, _method, "readonly")
for _target, _methods in TRADING_METHODS.items():
    for _method in _methods:
        RPC_METHODS[(_target, _method)] = RpcMethodSpec(_target, _method, "trading")


def allowed_methods(*, include_disabled: bool = False) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for spec in sorted(RPC_METHODS.values(), key=lambda item: (item.target, item.method)):
        if spec.enabled or include_disabled:
            result.setdefault(spec.target, []).append(spec.method)
    return result


def is_method_allowed(target: str, method: str) -> bool:
    spec = get_method_spec(target, method)
    return spec is not None and spec.enabled


def get_method_spec(target: str, method: str) -> RpcMethodSpec | None:
    return RPC_METHODS.get((target, method))


def method_specs(*, include_disabled: bool = True) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for spec in sorted(RPC_METHODS.values(), key=lambda item: (item.target, item.method)):
        if spec.enabled or include_disabled:
            result.setdefault(spec.target, []).append(
                {
                    "method": spec.method,
                    "level": spec.level,
                    "enabled": spec.enabled,
                }
            )
    return result
