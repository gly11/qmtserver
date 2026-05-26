from __future__ import annotations

from qmtserver.config import load_settings
from qmtserver.errors import QmtTargetNotConnectedError
from qmtserver.rpc.types import RpcResponse
from qmtserver.trading import DailyTradingLimits


class FakeTarget:
    non_callable = "not callable"

    def get_full_tick(self, codes: list[str]) -> dict[str, object]:
        return {"codes": codes}

    def get_sector_list(self) -> list[str]:
        return ["沪深A股"]

    def _private(self) -> str:
        return "secret"


class FakeTrader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def query_stock_asset(self, account: object) -> dict[str, object]:
        return {"account_id": getattr(account, "account_id", None)}

    def order_stock(self, *args: object) -> int:
        self.calls.append(("order_stock", args))
        return 10001

    def cancel_order_stock(self, *args: object) -> int:
        self.calls.append(("cancel_order_stock", args))
        return 0


class FakeService:
    def __init__(
        self,
        *,
        enable_trading: bool = False,
        trading_dry_run: bool = True,
        account_id: str | None = None,
        max_order_volume: int = 100000,
        max_order_amount: float = 1000000,
        allowed_symbols: str | None = None,
        blocked_symbols: str | None = None,
        daily_max_order_volume: int = 1000000,
        daily_max_order_amount: float = 5000000,
        require_trade_confirmation: bool = True,
        transparent_rpc: bool = False,
        transparent_rpc_targets: str = "xtdata",
        transparent_rpc_allow_trader: bool = False,
        transparent_rpc_allow_trading: bool = False,
    ) -> None:
        self.settings = load_settings(
            auto_connect=False,
            enable_trading=enable_trading,
            trading_dry_run=trading_dry_run,
            account_id=account_id,
            max_order_volume=max_order_volume,
            max_order_amount=max_order_amount,
            allowed_symbols=allowed_symbols,
            blocked_symbols=blocked_symbols,
            daily_max_order_volume=daily_max_order_volume,
            daily_max_order_amount=daily_max_order_amount,
            require_trade_confirmation=require_trade_confirmation,
            transparent_rpc=transparent_rpc,
            transparent_rpc_targets=transparent_rpc_targets,
            transparent_rpc_allow_trader=transparent_rpc_allow_trader,
            transparent_rpc_allow_trading=transparent_rpc_allow_trading,
        )
        self.connected = False
        self.trader = FakeTrader()
        self.daily_trading_limits = DailyTradingLimits()
        self.metrics: object | None = None

    def status(self) -> dict[str, object]:
        return {
            "ok": True,
            "quote": {"connected": self.connected},
            "trader": {"connected": self.connected},
            "lifecycle": {
                "state": "connected" if self.connected else "disconnected",
                "last_error": None,
            },
        }

    def connect(self) -> dict[str, object]:
        self.connected = True
        return self.status()

    def reconnect(self) -> dict[str, object]:
        self.connected = True
        return self.status()

    def disconnect(self) -> dict[str, object]:
        self.connected = False
        return self.status()

    def get_target(self, target: str) -> object:
        if target == "trader":
            return self.trader
        if target != "xtdata":
            raise QmtTargetNotConnectedError("target is not connected")
        return FakeTarget()


class DisconnectedTraderService(FakeService):
    def get_target(self, target: str) -> object:
        if target == "trader":
            raise QmtTargetNotConnectedError("target is not connected")
        return super().get_target(target)


def rpc_error_code(response: RpcResponse) -> str:
    error = response["error"]
    assert error is not None
    return error["code"]
