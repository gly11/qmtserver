from __future__ import annotations

from dataclasses import dataclass

from qmtserver.config import Settings
from qmtserver.errors import QmtAccountNotAllowedError, QmtTraderAccountRequiredError


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
