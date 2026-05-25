from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from threading import Lock
from typing import Any, Protocol

from qmtserver.config import Settings
from qmtserver.errors import (
    QmtAccountNotAllowedError,
    QmtDailyLimitExceededError,
    QmtOrderLimitExceededError,
    QmtSymbolNotAllowedError,
    QmtTradeConfirmationRequiredError,
    QmtTradingValidationError,
)

ORDER_METHODS = {"order_stock", "order_stock_async"}
CANCEL_METHODS = {"cancel_order_stock", "cancel_order_stock_async"}
ALLOWED_ORDER_TYPES = {23, 24}


class TradingCall(Protocol):
    target: str
    method: str
    args: list[Any]
    kwargs: dict[str, Any]


@dataclass(frozen=True)
class TradingPlan:
    dry_run: bool
    details: dict[str, object]
    kwargs: dict[str, Any]
    data: dict[str, object] | None = None


class DailyTradingLimits:
    def __init__(self) -> None:
        self._lock = Lock()
        self._day = date.today()
        self.order_volume = 0
        self.order_amount = 0.0

    def check_order(self, settings: Settings, details: dict[str, object]) -> None:
        volume = _detail_int(details, "order_volume")
        amount = _detail_float(details, "amount")
        with self._lock:
            self._reset_if_new_day()
            if self.order_volume + volume > settings.daily_max_order_volume:
                raise QmtDailyLimitExceededError(
                    "order would exceed QMT_DAILY_MAX_ORDER_VOLUME "
                    f"{settings.daily_max_order_volume}"
                )
            if self.order_amount + amount > settings.daily_max_order_amount:
                raise QmtDailyLimitExceededError(
                    "order would exceed QMT_DAILY_MAX_ORDER_AMOUNT "
                    f"{settings.daily_max_order_amount}"
                )

    def record_order(self, details: dict[str, object]) -> None:
        volume = _detail_int(details, "order_volume")
        amount = _detail_float(details, "amount")
        with self._lock:
            self._reset_if_new_day()
            self.order_volume += volume
            self.order_amount += amount

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            self._reset_if_new_day()
            return {
                "day": self._day.isoformat(),
                "order_volume": self.order_volume,
                "order_amount": self.order_amount,
            }

    def _reset_if_new_day(self) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            self.order_volume = 0
            self.order_amount = 0.0


def prepare_trading_call(
    settings: Settings,
    call: TradingCall,
    daily_limits: DailyTradingLimits | None = None,
) -> TradingPlan:
    if call.target != "trader":
        raise QmtTradingValidationError("Trading RPC target must be trader")

    call_kwargs = dict(call.kwargs)
    if call.method in ORDER_METHODS:
        detail = _validate_order(settings, call.args)
    elif call.method in CANCEL_METHODS:
        detail = _validate_cancel(settings, call.args)
    else:
        raise QmtTradingValidationError(f"Unsupported trading method: {call.method}")

    if settings.trading_dry_run:
        return TradingPlan(
            dry_run=True,
            details=detail,
            kwargs=call_kwargs,
            data={
                "dry_run": True,
                "target": call.target,
                "method": call.method,
                "validated": True,
                "would_call_xtquant": False,
                **detail,
            },
        )
    _validate_confirmation(settings, call_kwargs)
    if call.method in ORDER_METHODS and daily_limits is not None:
        daily_limits.check_order(settings, detail)
    return TradingPlan(dry_run=False, details=detail, kwargs=call_kwargs)


def _validate_order(settings: Settings, args: list[Any]) -> dict[str, object]:
    if len(args) < 6:
        raise QmtTradingValidationError(
            "order_stock requires account, stock_code, order_type, volume, price_type, price"
        )

    account_id = _validate_account(settings, args[0])
    stock_code = _require_nonempty_string(args[1], "stock_code")
    _validate_symbol(settings, stock_code)
    order_type = _require_int(args[2], "order_type")
    if order_type not in ALLOWED_ORDER_TYPES:
        raise QmtTradingValidationError(f"Unsupported order_type: {order_type}")

    volume = _require_positive_int(args[3], "order_volume")
    if volume > settings.max_order_volume:
        raise QmtOrderLimitExceededError(
            f"order_volume {volume} exceeds QMT_MAX_ORDER_VOLUME {settings.max_order_volume}"
        )

    price_type = _require_int(args[4], "price_type")
    if price_type < 0:
        raise QmtTradingValidationError("price_type must be non-negative")

    price = _require_nonnegative_number(args[5], "price")
    amount = price * volume
    if amount > settings.max_order_amount:
        raise QmtOrderLimitExceededError(
            f"order amount {amount} exceeds QMT_MAX_ORDER_AMOUNT {settings.max_order_amount}"
        )

    return {
        "account_id": account_id,
        "stock_code": stock_code,
        "order_type": order_type,
        "order_volume": volume,
        "price_type": price_type,
        "price": price,
        "amount": amount,
    }


def _validate_symbol(settings: Settings, stock_code: str) -> None:
    blocked = settings.trading_blocked_symbols()
    if stock_code in blocked:
        raise QmtSymbolNotAllowedError(f"Trading symbol is blocked: {stock_code}")
    allowed = settings.trading_allowed_symbols()
    if allowed and stock_code not in allowed:
        raise QmtSymbolNotAllowedError(f"Trading symbol is not allowed: {stock_code}")


def _validate_confirmation(settings: Settings, kwargs: dict[str, Any]) -> None:
    confirm = kwargs.pop("confirm", None)
    if not settings.require_trade_confirmation:
        return
    if confirm != settings.trade_confirmation_text:
        raise QmtTradeConfirmationRequiredError("Real trading requires confirmation text")


def _validate_cancel(settings: Settings, args: list[Any]) -> dict[str, object]:
    if len(args) < 2:
        raise QmtTradingValidationError("cancel_order_stock requires account and order_id")

    account_id = _validate_account(settings, args[0])
    market = None
    order_id_value = args[1]
    if len(args) >= 3:
        market = _require_int(args[1], "market")
        order_id_value = args[2]
    order_id = _require_positive_int(order_id_value, "order_id")

    detail: dict[str, object] = {
        "account_id": account_id,
        "order_id": order_id,
    }
    if market is not None:
        detail["market"] = market
    return detail


def _validate_account(settings: Settings, account: Any) -> str:
    account_id = _extract_account_id(account)
    if not account_id:
        raise QmtTradingValidationError("account must include account_id")

    allowed_accounts = settings.trading_allowed_accounts()
    if not allowed_accounts:
        raise QmtAccountNotAllowedError("No trading account is configured")
    if account_id not in allowed_accounts:
        raise QmtAccountNotAllowedError(f"Trading account is not allowed: {account_id}")
    return account_id


def _extract_account_id(account: Any) -> str | None:
    if isinstance(account, dict):
        if account.get("__type__") != "StockAccount":
            raise QmtTradingValidationError("account must be a StockAccount")
        account_id = account.get("account_id")
        return str(account_id) if account_id else None
    account_id = getattr(account, "account_id", None)
    return str(account_id) if account_id else None


def _require_nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QmtTradingValidationError(f"{name} must be a non-empty string")
    return value


def _require_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise QmtTradingValidationError(f"{name} must be an integer")
    return value


def _require_positive_int(value: Any, name: str) -> int:
    number = _require_int(value, name)
    if number <= 0:
        raise QmtTradingValidationError(f"{name} must be positive")
    return number


def _require_nonnegative_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise QmtTradingValidationError(f"{name} must be a number")
    number = float(value)
    if number < 0:
        raise QmtTradingValidationError(f"{name} must be non-negative")
    return number


def _detail_int(details: dict[str, object], key: str) -> int:
    value = details.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _detail_float(details: dict[str, object], key: str) -> float:
    value = details.get(key, 0.0)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)
