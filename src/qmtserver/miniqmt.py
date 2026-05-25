from __future__ import annotations

import contextlib
import platform
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QuoteCheckConfig:
    code: str = "000001.SZ"
    ip: str = ""
    port: int | None = None


@dataclass(frozen=True)
class TraderCheckConfig:
    userdata: Path
    account_id: str | None = None
    account_type: str = "STOCK"
    session_id: int | None = None
    timeout_ms: int = 5000


class MiniQmtCallback:
    def __init__(self) -> None:
        self.events: list[str] = []

    def on_connected(self) -> None:
        self.events.append("connected")

    def on_disconnected(self) -> None:
        self.events.append("disconnected")

    def on_account_status(self, status: Any) -> None:
        self.events.append(f"account_status:{_to_plain(status)}")

    def on_order_error(self, order_error: Any) -> None:
        self.events.append(f"order_error:{_to_plain(order_error)}")

    def on_cancel_error(self, cancel_error: Any) -> None:
        self.events.append(f"cancel_error:{_to_plain(cancel_error)}")


def build_connectivity_report(
    *,
    quote: QuoteCheckConfig | None,
    trader: TraderCheckConfig | None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": True,
        "python": {
            "version": sys.version.split()[0],
            "implementation": platform.python_implementation(),
        },
        "xtquant": check_xtquant_import(),
        "quote": None,
        "trader": None,
    }

    if not report["xtquant"]["ok"]:
        report["ok"] = False
        return report

    if quote is not None:
        report["quote"] = check_quote_connection(quote)
        report["ok"] = report["ok"] and report["quote"]["ok"]

    if trader is not None:
        report["trader"] = check_trader_connection(trader)
        report["ok"] = report["ok"] and report["trader"]["ok"]

    return report


def check_xtquant_import() -> dict[str, Any]:
    try:
        import xtquant

        package_file = Path(xtquant.__file__).resolve()
        return {
            "ok": True,
            "path": str(package_file.parent),
            "version": getattr(xtquant, "__version__", None),
        }
    except Exception as exc:
        return {"ok": False, "error": _format_exception(exc)}


def check_quote_connection(config: QuoteCheckConfig) -> dict[str, Any]:
    try:
        from xtquant import xtdata

        client = xtdata.reconnect(
            ip=config.ip,
            port=config.port,
            remember_if_success=True,
        )
        connected = bool(client and client.is_connected())
        tick: Any = None
        if connected and config.code:
            with contextlib.suppress(Exception):
                tick = xtdata.get_full_tick([config.code])

        return {
            "ok": connected,
            "connected": connected,
            "code": config.code,
            "tick": _to_plain(tick),
        }
    except Exception as exc:
        return {"ok": False, "connected": False, "error": _format_exception(exc)}


def check_trader_connection(config: TraderCheckConfig) -> dict[str, Any]:
    userdata = config.userdata.expanduser().resolve()
    if not userdata.exists():
        return {
            "ok": False,
            "connected": False,
            "userdata": str(userdata),
            "error": f"userdata path does not exist: {userdata}",
        }

    trader = None
    started = False
    callback = MiniQmtCallback()

    try:
        from xtquant.xttrader import XtQuantTrader
        from xtquant.xttype import StockAccount

        session_id = config.session_id or _make_session_id()
        trader = XtQuantTrader(str(userdata), session_id, callback)
        trader.set_timeout(config.timeout_ms)
        trader.start()
        started = True
        connect_result = trader.connect()
        connected = connect_result == 0

        result: dict[str, Any] = {
            "ok": connected,
            "connected": connected,
            "connect_result": connect_result,
            "userdata": str(userdata),
            "session_id": session_id,
            "callback_events": callback.events,
            "account_infos": None,
            "account_status": None,
            "subscribe_result": None,
            "asset": None,
        }

        if connected:
            with contextlib.suppress(Exception):
                result["account_infos"] = _to_plain(trader.query_account_infos())
            with contextlib.suppress(Exception):
                result["account_status"] = _to_plain(trader.query_account_status())

            if config.account_id:
                account = StockAccount(config.account_id, config.account_type)
                result["subscribe_result"] = _to_plain(trader.subscribe(account))
                result["asset"] = _to_plain(trader.query_stock_asset(account))

        return result
    except Exception as exc:
        return {
            "ok": False,
            "connected": False,
            "userdata": str(userdata),
            "callback_events": callback.events,
            "error": _format_exception(exc),
        }
    finally:
        if trader is not None and started:
            with contextlib.suppress(Exception):
                trader.stop()


def _make_session_id() -> int:
    return int(time.time()) % 1_000_000_000 + random.randint(1, 999)


def _format_exception(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _to_plain(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_to_plain(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            key: _to_plain(item) for key, item in vars(value).items() if not key.startswith("_")
        }
    return repr(value)
