from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.events import EventBus
from qmtserver.orders import OrderStore

router = APIRouter(tags=["orders"])


@router.get("/orders")
def orders(request: Request, limit: int | None = None) -> dict[str, object]:
    service = get_qmt_service(request)
    store = _order_store(request, service)
    return {"ok": True, "data": store.orders(limit)}


@router.get("/orders/{order_id}")
def order(request: Request, order_id: str) -> dict[str, object]:
    service = get_qmt_service(request)
    store = _order_store(request, service)
    record = store.get_order(order_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": f"Order not found: {order_id}"},
        )
    return {"ok": True, "data": record}


@router.get("/trades")
def trades(request: Request, limit: int | None = None) -> dict[str, object]:
    service = get_qmt_service(request)
    store = _order_store(request, service)
    return {"ok": True, "data": store.trades(limit)}


@router.get("/events/recent")
def recent_events(
    request: Request,
    types: str | None = None,
    symbol: str | None = None,
    symbols: str | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    get_qmt_service(request)
    event_bus: EventBus = request.app.state.event_bus
    event_types = _parse_types(types)
    event_symbols = _parse_types(symbols or symbol)
    return {
        "ok": True,
        "data": event_bus.recent_events(
            event_types=event_types,
            symbols=event_symbols,
            limit=limit,
        ),
    }


def _order_store(request: Request, service: object) -> OrderStore:
    store = getattr(service, "order_store", None)
    if isinstance(store, OrderStore):
        return store
    return request.app.state.order_store


def _parse_types(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}
