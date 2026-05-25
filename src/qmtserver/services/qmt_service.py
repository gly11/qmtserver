from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from qmtserver.config import Settings
from qmtserver.miniqmt import MiniQmtCallback, check_xtquant_import


@dataclass
class QmtService:
    settings: Settings
    quote_client: Any = None
    trader: Any = None
    callback: MiniQmtCallback = field(default_factory=MiniQmtCallback)
    quote_connected: bool = False
    trader_connected: bool = False
    account_subscribed: bool = False
    last_error: str | None = None
    last_success_at: str | None = None

    def connect(self) -> dict[str, Any]:
        self.shutdown()
        self.last_error = None
        self.quote_connected = False
        self.trader_connected = False
        self.account_subscribed = False

        try:
            self._connect_quote()
            self._connect_trader()
            self._mark_success()
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"

        return self.status()

    def shutdown(self) -> None:
        if self.trader is not None:
            with contextlib.suppress(Exception):
                self.trader.stop()
        self.trader = None
        self.trader_connected = False
        self.account_subscribed = False

        if self.quote_client is not None:
            with contextlib.suppress(Exception):
                from xtquant import xtdata

                xtdata.disconnect()
        self.quote_client = None
        self.quote_connected = False

    def status(self) -> dict[str, Any]:
        xtquant = check_xtquant_import()
        return {
            "ok": xtquant["ok"] and self.last_error is None,
            "xtquant": xtquant,
            "quote": {
                "connected": self.quote_connected,
                "code": self.settings.quote_code,
            },
            "trader": {
                "connected": self.trader_connected,
                "account_id": self.settings.account_id,
                "account_type": self.settings.account_type,
                "account_subscribed": self.account_subscribed,
            },
            "last_error": self.last_error,
            "last_success_at": self.last_success_at,
        }

    def get_target(self, target: str) -> Any:
        if target == "xtdata":
            from xtquant import xtdata

            return xtdata
        if target == "trader":
            if self.trader is None or not self.trader_connected:
                raise RuntimeError("trader is not connected")
            return self.trader
        raise ValueError(f"unsupported rpc target: {target}")

    def _connect_quote(self) -> None:
        from xtquant import xtdata

        self.quote_client = xtdata.reconnect()
        self.quote_connected = bool(self.quote_client and self.quote_client.is_connected())
        if not self.quote_connected:
            raise RuntimeError("quote connection failed")

    def _connect_trader(self) -> None:
        if self.settings.userdata is None:
            return

        userdata = self.settings.userdata.expanduser().resolve()
        if not userdata.exists():
            raise FileNotFoundError(f"userdata path does not exist: {userdata}")

        from xtquant.xttrader import XtQuantTrader
        from xtquant.xttype import StockAccount

        try:
            self.trader = XtQuantTrader(str(userdata), _session_id(), self.callback)
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
            if self.trader is not None:
                with contextlib.suppress(Exception):
                    self.trader.stop()
            self.trader = None
            self.trader_connected = False
            self.account_subscribed = False
            raise

    def _mark_success(self) -> None:
        self.last_success_at = datetime.now(UTC).isoformat()


def _session_id() -> int:
    return int(datetime.now(UTC).timestamp()) % 1_000_000_000
