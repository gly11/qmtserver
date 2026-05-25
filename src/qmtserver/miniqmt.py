from __future__ import annotations

import contextlib
import platform
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qmtserver.events import EventBus
    from qmtserver.orders import OrderStore


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
    def __init__(
        self,
        event_bus: EventBus | None = None,
        order_store: OrderStore | None = None,
    ) -> None:
        self.events: list[str] = []
        self.event_bus = event_bus
        self.order_store = order_store

    def on_connected(self) -> None:
        self.events.append("connected")
        self._publish("qmt_connected")

    def on_disconnected(self) -> None:
        self.events.append("disconnected")
        self._publish("qmt_disconnected")

    def on_account_status(self, status: Any) -> None:
        data = _to_plain(status)
        self.events.append(f"account_status:{data}")
        self._publish("account_status", data)

    def on_stock_order(self, order: Any) -> None:
        data = _to_plain(order)
        self.events.append(f"stock_order:{data}")
        payload = _dict_payload(data)
        if self.order_store is not None:
            self.order_store.record_order(payload)
        self._publish("stock_order", payload)

    def on_stock_trade(self, trade: Any) -> None:
        data = _to_plain(trade)
        self.events.append(f"stock_trade:{data}")
        payload = _dict_payload(data)
        if self.order_store is not None:
            self.order_store.record_trade(payload)
        self._publish("stock_trade", payload)

    def on_order_error(self, order_error: Any) -> None:
        data = _to_plain(order_error)
        self.events.append(f"order_error:{data}")
        payload = _dict_payload(data)
        if self.order_store is not None:
            self.order_store.record_error("order_error", payload)
        self._publish("order_error", payload)

    def on_cancel_error(self, cancel_error: Any) -> None:
        data = _to_plain(cancel_error)
        self.events.append(f"cancel_error:{data}")
        payload = _dict_payload(data)
        if self.order_store is not None:
            self.order_store.record_error("cancel_error", payload)
        self._publish("cancel_error", payload)

    def _publish(self, event_type: str, data: Any = None) -> None:
        if self.event_bus is None:
            return
        payload = data if isinstance(data, dict) else {"value": data} if data is not None else {}
        self.event_bus.publish_threadsafe(event_type, payload, {"source": "xtquant"})


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


def _dict_payload(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {"value": value}
