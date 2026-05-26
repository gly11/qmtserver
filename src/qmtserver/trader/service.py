from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qmtserver import __version__
from qmtserver.config import Settings
from qmtserver.errors import (
    QmtAccountNotAllowedError,
    QmtServerError,
    QmtTraderAccountRequiredError,
)
from qmtserver.miniqmt import check_xtquant_import
from qmtserver.rpc.serializers import convert_input
from qmtserver.trader.models import (
    TRADER_READONLY_SCHEMA,
    normalize_account_status,
    normalize_asset,
    normalize_order,
    normalize_position,
    normalize_trade,
)


@dataclass(frozen=True)
class ResolvedStockAccount:
    account_id: str
    account_type: str


def resolve_stock_account(
    settings: Settings,
    *,
    account_id: str | None,
    account_type: str | None,
) -> ResolvedStockAccount:
    resolved_account_id = account_id or settings.account_id
    if not resolved_account_id:
        raise QmtTraderAccountRequiredError("account_id is required for trader query")

    allowed = settings.trading_allowed_accounts()
    if allowed and resolved_account_id not in allowed:
        raise QmtAccountNotAllowedError(f"Trading account is not allowed: {resolved_account_id}")

    return ResolvedStockAccount(
        account_id=resolved_account_id,
        account_type=account_type or settings.account_type,
    )


class TraderReadonlyService:
    def __init__(self, qmt_service: Any) -> None:
        self.qmt_service = qmt_service
        self.settings: Settings = qmt_service.settings

    def account_status(self) -> dict[str, Any]:
        try:
            trader = self.qmt_service.get_target("trader")
            data = [normalize_account_status(item) for item in trader.query_account_status()]
            data = _filter_allowed_account_statuses(data, self.settings.trading_allowed_accounts())
            return self._success({"statuses": data}, account=None)
        except Exception as exc:
            return self._failure(exc, account=None)

    def asset(
        self,
        *,
        account_id: str | None,
        account_type: str | None,
    ) -> dict[str, Any]:
        account: ResolvedStockAccount | None = None
        try:
            trader = self.qmt_service.get_target("trader")
            account = self._resolve_account(account_id, account_type)
            data = normalize_asset(trader.query_stock_asset(_stock_account(account)))
            return self._success({"asset": data}, account=account)
        except Exception as exc:
            return self._failure(exc, account=account)

    def positions(
        self,
        *,
        account_id: str | None,
        account_type: str | None,
    ) -> dict[str, Any]:
        account: ResolvedStockAccount | None = None
        try:
            trader = self.qmt_service.get_target("trader")
            account = self._resolve_account(account_id, account_type)
            data = [
                normalize_position(item)
                for item in trader.query_stock_positions(_stock_account(account))
            ]
            return self._success({"positions": data}, account=account)
        except Exception as exc:
            return self._failure(exc, account=account)

    def orders(
        self,
        *,
        account_id: str | None,
        account_type: str | None,
        cancelable_only: bool = False,
    ) -> dict[str, Any]:
        account: ResolvedStockAccount | None = None
        try:
            trader = self.qmt_service.get_target("trader")
            account = self._resolve_account(account_id, account_type)
            data = [
                normalize_order(item)
                for item in trader.query_stock_orders(
                    _stock_account(account),
                    cancelable_only,
                )
            ]
            return self._success(
                {"orders": data, "cancelable_only": cancelable_only},
                account=account,
            )
        except Exception as exc:
            return self._failure(exc, account=account)

    def trades(
        self,
        *,
        account_id: str | None,
        account_type: str | None,
    ) -> dict[str, Any]:
        account: ResolvedStockAccount | None = None
        try:
            trader = self.qmt_service.get_target("trader")
            account = self._resolve_account(account_id, account_type)
            data = [
                normalize_trade(item) for item in trader.query_stock_trades(_stock_account(account))
            ]
            return self._success({"trades": data}, account=account)
        except Exception as exc:
            return self._failure(exc, account=account)

    def _resolve_account(
        self,
        account_id: str | None,
        account_type: str | None,
    ) -> ResolvedStockAccount:
        return resolve_stock_account(
            self.settings,
            account_id=account_id,
            account_type=account_type,
        )

    def _success(
        self,
        data: dict[str, Any],
        *,
        account: ResolvedStockAccount | None,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "data": data,
            "error": None,
            "meta": self._meta(account),
        }

    def _failure(
        self,
        exc: Exception,
        *,
        account: ResolvedStockAccount | None,
    ) -> dict[str, Any]:
        code = exc.code if isinstance(exc, QmtServerError) else "QMT_SERVER_ERROR"
        return {
            "ok": False,
            "data": None,
            "error": {"code": code, "message": str(exc)},
            "meta": self._meta(account),
        }

    def _meta(self, account: ResolvedStockAccount | None) -> dict[str, Any]:
        xtquant = check_xtquant_import()
        return {
            "schema": TRADER_READONLY_SCHEMA,
            "qmtserver_version": __version__,
            "xtquant_version": xtquant.get("version") if xtquant.get("ok") else None,
            "account_id": _mask_account(account.account_id) if account else None,
            "account_type": account.account_type if account else None,
        }


def _stock_account(account: ResolvedStockAccount) -> Any:
    return convert_input(
        {
            "__type__": "StockAccount",
            "account_id": account.account_id,
            "account_type": account.account_type,
        }
    )


def _mask_account(account_id: str) -> str:
    if len(account_id) <= 6:
        return "***"
    return f"{account_id[:3]}****{account_id[-3:]}"


def _filter_allowed_account_statuses(
    statuses: list[dict[str, Any]],
    allowed_accounts: set[str],
) -> list[dict[str, Any]]:
    if not allowed_accounts:
        return statuses
    return [item for item in statuses if item.get("account_id") in allowed_accounts]
