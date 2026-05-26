from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.market import MarketService
from qmtserver.services import QmtService

router = APIRouter(prefix="/market", tags=["market"])
QmtServiceDep = Annotated[QmtService, Depends(get_qmt_service)]


@router.get("/capabilities")
def capabilities(service: QmtServiceDep) -> dict[str, object]:
    return MarketService(service).capabilities()


@router.get("/bars/daily")
def daily_bars(
    service: QmtServiceDep,
    symbols: str | None = None,
    start: str | None = None,
    end: str | None = None,
    adjust: str = "none",
) -> dict[str, object]:
    return MarketService(service).daily_bars(
        symbols=symbols,
        start=start,
        end=end,
        adjust=adjust,
    )


@router.get("/bars/intraday")
def intraday_bars(
    service: QmtServiceDep,
    symbols: str | None = None,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
    adjust: str = "none",
) -> dict[str, object]:
    return MarketService(service).intraday_bars(
        symbols=symbols,
        period=period,
        start=start,
        end=end,
        adjust=adjust,
    )
