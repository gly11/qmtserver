from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.data_quality.service import expected_weekdays

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/calendar")
def calendar(
    request: Request,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, object]:
    get_qmt_service(request)
    dates = expected_weekdays(start, end)
    return _response("reference.calendar.v1", {"dates": dates, "source": "weekday"})


@router.get("/universe")
def universe(request: Request, name: str = "all_a") -> dict[str, object]:
    service = get_qmt_service(request)
    try:
        xtdata = service.get_target("xtdata")
        symbols = xtdata.get_stock_list_in_sector("沪深A股" if name == "all_a" else name)
    except Exception:
        symbols = []
    return _response("reference.universe.v1", {"name": name, "symbols": symbols})


@router.get("/instruments")
def instruments(request: Request, symbols: str | None = None) -> dict[str, object]:
    service = get_qmt_service(request)
    parsed = [item.strip() for item in (symbols or "").split(",") if item.strip()]
    instruments_data: list[dict[str, Any]] = []
    try:
        xtdata = service.get_target("xtdata")
        for symbol in parsed:
            detail = xtdata.get_instrument_detail(symbol)
            if isinstance(detail, dict):
                item = {"symbol": symbol, **detail}
            else:
                item = {"symbol": symbol, "detail": detail}
            instruments_data.append(item)
    except Exception:
        instruments_data = [{"symbol": symbol} for symbol in parsed]
    return _response("reference.instruments.v1", {"instruments": instruments_data})


def _response(schema: str, data: dict[str, Any]) -> dict[str, object]:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "meta": {"schema": schema, "generated_at": datetime.now(UTC).isoformat()},
    }
