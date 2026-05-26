from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.services import QmtService
from qmtserver.trader import TraderReadonlyService

router = APIRouter(prefix="/trader", tags=["trader"])
QmtServiceDep = Annotated[QmtService, Depends(get_qmt_service)]


@router.get("/account-status")
def account_status(service: QmtServiceDep) -> dict[str, object]:
    return TraderReadonlyService(service).account_status()


@router.get("/asset")
def asset(
    service: QmtServiceDep,
    account_id: str | None = None,
    account_type: str | None = None,
) -> dict[str, object]:
    return TraderReadonlyService(service).asset(
        account_id=account_id,
        account_type=account_type,
    )


@router.get("/positions")
def positions(
    service: QmtServiceDep,
    account_id: str | None = None,
    account_type: str | None = None,
) -> dict[str, object]:
    return TraderReadonlyService(service).positions(
        account_id=account_id,
        account_type=account_type,
    )


@router.get("/orders")
def orders(
    service: QmtServiceDep,
    account_id: str | None = None,
    account_type: str | None = None,
    cancelable_only: bool = False,
) -> dict[str, object]:
    return TraderReadonlyService(service).orders(
        account_id=account_id,
        account_type=account_type,
        cancelable_only=cancelable_only,
    )


@router.get("/trades")
def trades(
    service: QmtServiceDep,
    account_id: str | None = None,
    account_type: str | None = None,
) -> dict[str, object]:
    return TraderReadonlyService(service).trades(
        account_id=account_id,
        account_type=account_type,
    )
