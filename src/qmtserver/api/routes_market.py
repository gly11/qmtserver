from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends

from qmtserver.api.dependencies import get_market_subscription_service, get_qmt_service
from qmtserver.data_quality.service import quality_response
from qmtserver.errors import QmtInvalidSubscriptionRequestError, QmtServerError
from qmtserver.market import MarketService, MarketSubscriptionService
from qmtserver.services import QmtService

router = APIRouter(prefix="/market", tags=["market"])
QmtServiceDep = Annotated[QmtService, Depends(get_qmt_service)]
MarketSubscriptionServiceDep = Annotated[
    MarketSubscriptionService,
    Depends(get_market_subscription_service),
]
SubscriptionPayload = Annotated[dict[str, Any], Body()]


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


@router.get("/bars/daily/quality")
def daily_bars_quality(
    service: QmtServiceDep,
    symbols: str | None = None,
    start: str | None = None,
    end: str | None = None,
    adjust: str = "none",
) -> dict[str, object]:
    response = MarketService(service).daily_bars(
        symbols=symbols,
        start=start,
        end=end,
        adjust=adjust,
    )
    if not response["ok"]:
        return response
    return quality_response(response["data"]["bars"], start=start, end=end)


@router.post("/subscriptions")
def create_subscription(
    service: MarketSubscriptionServiceDep,
    payload: SubscriptionPayload,
) -> dict[str, Any]:
    try:
        symbols = payload.get("symbols")
        if not isinstance(symbols, list):
            raise QmtInvalidSubscriptionRequestError("symbols must be a list")
        period = payload.get("period", "tick")
        if not isinstance(period, str):
            raise QmtInvalidSubscriptionRequestError("period must be a string")
        subscription = service.create(symbols=[str(item) for item in symbols], period=period)
        return _success(subscription.as_dict())
    except QmtServerError as exc:
        return _error(exc)


@router.get("/subscriptions")
def list_subscriptions(service: MarketSubscriptionServiceDep) -> dict[str, Any]:
    subscriptions = [item.as_dict() for item in service.list_subscriptions()]
    return _success({"subscriptions": subscriptions})


@router.get("/subscriptions/{subscription_id}")
def get_subscription(
    subscription_id: str,
    service: MarketSubscriptionServiceDep,
) -> dict[str, Any]:
    try:
        return _success(service.get(subscription_id).as_dict())
    except QmtServerError as exc:
        return _error(exc)


@router.get("/subscriptions/{subscription_id}/diagnostics")
def get_subscription_diagnostics(
    subscription_id: str,
    service: MarketSubscriptionServiceDep,
) -> dict[str, Any]:
    try:
        return _success(service.diagnostics(subscription_id))
    except QmtServerError as exc:
        return _error(exc)


@router.delete("/subscriptions/{subscription_id}")
def stop_subscription(
    subscription_id: str,
    service: MarketSubscriptionServiceDep,
) -> dict[str, Any]:
    try:
        return _success(service.stop(subscription_id).as_dict())
    except QmtServerError as exc:
        return _error(exc)


@router.post("/subscriptions/{subscription_id}/recover")
def recover_subscription(
    subscription_id: str,
    service: MarketSubscriptionServiceDep,
) -> dict[str, Any]:
    try:
        return _success(service.recover(subscription_id).as_dict())
    except QmtServerError as exc:
        return _error(exc)


@router.get("/quotes/latest")
def latest_quotes(
    service: MarketSubscriptionServiceDep,
    symbols: str | None = None,
) -> dict[str, Any]:
    try:
        return _success(service.latest_quotes(_symbol_list(symbols)))
    except QmtServerError as exc:
        return _error(exc)


def _success(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def _error(exc: QmtServerError) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {"code": exc.code, "message": str(exc)},
    }


def _symbol_list(symbols: str | None) -> list[str] | None:
    if symbols is None:
        return None
    return [item.strip() for item in symbols.split(",") if item.strip()]
