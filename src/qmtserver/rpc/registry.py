from __future__ import annotations

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


def allowed_methods() -> dict[str, list[str]]:
    return {
        target: sorted(methods)
        for target, methods in sorted(READONLY_METHODS.items(), key=lambda item: item[0])
    }


def is_method_allowed(target: str, method: str) -> bool:
    return method in READONLY_METHODS.get(target, set())
