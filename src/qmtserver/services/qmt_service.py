from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from qmtserver.config import Settings
from qmtserver.errors import QmtTargetNotConnectedError, QmtTargetNotFoundError
from qmtserver.events import EventBus
from qmtserver.miniqmt import MiniQmtCallback, check_xtquant_import
from qmtserver.observability import Metrics
from qmtserver.trading import DailyTradingLimits


@dataclass
class LifecycleState:
    state: str = "new"
    last_connect_at: str | None = None
    last_disconnect_at: str | None = None
    last_success_at: str | None = None
    last_error_at: str | None = None
    last_error: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "state": self.state,
            "last_connect_at": self.last_connect_at,
            "last_disconnect_at": self.last_disconnect_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error": self.last_error,
        }


@dataclass
class QmtService:
    settings: Settings
    event_bus: EventBus | None = None
    metrics: Metrics | None = None
    daily_trading_limits: DailyTradingLimits = field(default_factory=DailyTradingLimits)
    quote_client: Any = None
    trader: Any = None
    callback: MiniQmtCallback | None = None
    quote_connected: bool = False
    trader_connected: bool = False
    account_subscribed: bool = False
    session_id: int | None = None
    quote_address: str | None = None
    quote_data_dir: str | None = None
    lifecycle: LifecycleState = field(default_factory=LifecycleState)

    def __post_init__(self) -> None:
        if self.callback is None:
            self.callback = MiniQmtCallback(self.event_bus)

    def connect(self) -> dict[str, Any]:
        self.disconnect()
        self.lifecycle.state = "connecting"
        self.lifecycle.last_connect_at = _now()
        self.lifecycle.last_error = None
        self.lifecycle.last_error_at = None

        try:
            if self.settings.connect_quote:
                self._connect_quote()
            if self.settings.connect_trader:
                self._connect_trader()
            self._mark_success()
            self._publish_lifecycle_event("qmt_connected")
        except Exception as exc:
            self._mark_error(exc)
            self._publish_lifecycle_event("qmt_error", {"error": self.lifecycle.last_error})

        return self.status()

    def reconnect(self) -> dict[str, Any]:
        self.disconnect()
        return self.connect()

    def disconnect(self) -> dict[str, Any]:
        self._stop_trader()
        self._disconnect_quote()
        self.lifecycle.state = "disconnected"
        self.lifecycle.last_disconnect_at = _now()
        self._publish_lifecycle_event("qmt_disconnected")
        return self.status()

    def shutdown(self) -> None:
        self.disconnect()

    def is_quote_connected(self) -> bool:
        return self.quote_connected

    def is_trader_connected(self) -> bool:
        return self.trader_connected

    def _stop_trader(self) -> None:
        if self.trader is not None:
            with contextlib.suppress(Exception):
                self.trader.stop()
        self.trader = None
        self.trader_connected = False
        self.account_subscribed = False
        self.session_id = None

    def _disconnect_quote(self) -> None:
        if self.quote_client is not None:
            with contextlib.suppress(Exception):
                from xtquant import xtdata

                xtdata.disconnect()
        self.quote_client = None
        self.quote_connected = False
        self.quote_address = None
        self.quote_data_dir = None

    def status(self) -> dict[str, Any]:
        xtquant = check_xtquant_import()
        quote_expected = self.settings.connect_quote
        trader_expected = self.settings.connect_trader and self.settings.userdata is not None
        return {
            "ok": xtquant["ok"] and self.lifecycle.last_error is None,
            "xtquant": xtquant,
            "quote": {
                "connected": self.quote_connected,
                "code": self.settings.quote_code,
                "address": self.quote_address,
                "data_dir": self.quote_data_dir,
                "enabled": quote_expected,
            },
            "trader": {
                "connected": self.trader_connected,
                "session_id": self.session_id,
                "userdata": str(self.settings.userdata) if self.settings.userdata else None,
                "account_id": self.settings.account_id,
                "account_type": self.settings.account_type,
                "account_subscribed": self.account_subscribed,
                "enabled": self.settings.connect_trader,
            },
            "lifecycle": self.lifecycle.as_dict(),
            "last_error": self.lifecycle.last_error,
            "last_success_at": self.lifecycle.last_success_at,
            "ready": {
                "quote": (not quote_expected) or self.quote_connected,
                "trader": (not trader_expected) or self.trader_connected,
            },
        }

    def get_target(self, target: str) -> Any:
        if target == "xtdata":
            if not self.quote_connected:
                raise QmtTargetNotConnectedError("xtdata target is not connected")
            from xtquant import xtdata

            return xtdata
        if target == "trader":
            if self.trader is None or not self.trader_connected:
                raise QmtTargetNotConnectedError("trader target is not connected")
            return self.trader
        raise QmtTargetNotFoundError(f"unsupported rpc target: {target}")

    def _connect_quote(self) -> None:
        from xtquant import xtdata

        self.quote_client = xtdata.reconnect()
        self.quote_connected = bool(self.quote_client and self.quote_client.is_connected())
        if not self.quote_connected:
            raise RuntimeError("quote connection failed")
        self.quote_address = _read_client_value(self.quote_client, "get_server_addr")
        self.quote_data_dir = _read_client_value(self.quote_client, "get_data_dir")

    def _connect_trader(self) -> None:
        if self.settings.userdata is None:
            return

        userdata = self.settings.userdata.expanduser().resolve()
        if not userdata.exists():
            raise FileNotFoundError(f"userdata path does not exist: {userdata}")

        from xtquant.xttrader import XtQuantTrader
        from xtquant.xttype import StockAccount

        try:
            assert self.callback is not None
            self.session_id = _session_id()
            self.trader = XtQuantTrader(str(userdata), self.session_id, self.callback)
            self.trader.set_timeout(self.settings.trader_timeout_ms)
            self.trader.start()
            connect_result = self.trader.connect()
            self.trader_connected = connect_result == 0
            if not self.trader_connected:
                raise RuntimeError(f"trader connection failed: {connect_result}")

            if self.settings.account_id:
                account = StockAccount(self.settings.account_id, self.settings.account_type)
                subscribe_result = self.trader.subscribe(account)
                self.account_subscribed = subscribe_result == 0
        except Exception:
            self._stop_trader()
            raise

    def _mark_success(self) -> None:
        if self.quote_connected and (
            self.trader_connected
            or self.settings.userdata is None
            or not self.settings.connect_trader
        ):
            self.lifecycle.state = "connected"
        else:
            self.lifecycle.state = "partial"
        self.lifecycle.last_success_at = _now()
        self.lifecycle.last_error = None
        self.lifecycle.last_error_at = None

    def _mark_error(self, exc: Exception) -> None:
        self.lifecycle.state = (
            "partial" if self.quote_connected or self.trader_connected else "error"
        )
        self.lifecycle.last_error = f"{type(exc).__name__}: {exc}"
        self.lifecycle.last_error_at = _now()

    def _publish_lifecycle_event(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self.event_bus is None:
            return
        payload = data or {"status": self.status()}
        self.event_bus.publish_threadsafe(event_type, payload, {"source": "qmtserver"})


def _session_id() -> int:
    return int(datetime.now(UTC).timestamp()) % 1_000_000_000


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read_client_value(client: Any, method_name: str) -> str | None:
    method = getattr(client, method_name, None)
    if method is None:
        return None
    with contextlib.suppress(Exception):
        value = method()
        if value is not None:
            return str(value)
    return None
