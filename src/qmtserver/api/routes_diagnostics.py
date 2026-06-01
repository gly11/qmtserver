from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from qmtserver import __version__
from qmtserver.api.dependencies import get_qmt_service
from qmtserver.miniqmt import check_xtquant_import
from qmtserver.runtime_health import build_runtime_health

router = APIRouter(tags=["diagnostics"])


@router.get("/diagnostics")
def diagnostics(request: Request) -> dict[str, object]:
    service = get_qmt_service(request)
    symbol = service.settings.quote_code
    qmt_status = service.status()
    subscription_service = getattr(request.app.state, "market_subscription_service", None)
    return {
        "ok": True,
        "data": {
            "qmt": qmt_status,
            "runtime_health": build_runtime_health(
                qmt_status,
                subscription_service=subscription_service,
            ),
            "clock": {
                "server_time": datetime.now(UTC).isoformat(),
                "timezone": "UTC",
            },
            "version": {
                "qmtserver": __version__,
                "xtquant": check_xtquant_import(),
            },
            "sample": _sample_tick(service, symbol),
        },
        "error": None,
        "meta": {},
    }


def _sample_tick(service: Any, symbol: str) -> dict[str, Any]:
    try:
        xtdata = service.get_target("xtdata")
        return {"ok": True, "symbol": symbol, "data": xtdata.get_full_tick([symbol])}
    except Exception as exc:
        return {
            "ok": False,
            "symbol": symbol,
            "error": {"code": type(exc).__name__, "message": str(exc)},
        }
