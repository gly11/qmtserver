from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from qmtserver import __version__
from qmtserver.api.dependencies import get_qmt_service
from qmtserver.data.backend import create_data_backend
from qmtserver.data.jobs import create_data_job_service
from qmtserver.data.maintenance import DataMaintenanceService
from qmtserver.data.repository import DataJobRepository
from qmtserver.errors import QmtServerError
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
            "data_lake": _data_lake_diagnostics(request),
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


def _data_lake_diagnostics(request: Request) -> dict[str, Any]:
    try:
        data_job_service = _get_data_job_service(request)
        maintenance = _get_data_maintenance_service(request)
        return {
            "schema": "market.data.diagnostics.v1",
            "health": maintenance.health_summary(),
            "jobs": data_job_service.diagnostics(),
            "error": None,
        }
    except QmtServerError as exc:
        return {
            "schema": "market.data.diagnostics.v1",
            "health": {
                "schema": "market.data.health.v1",
                "status": "unavailable",
                "reason": exc.code,
            },
            "jobs": None,
            "error": {"code": exc.code, "message": str(exc)},
        }


def _get_data_job_service(request: Request) -> Any:
    if hasattr(request.app.state, "data_job_service"):
        return request.app.state.data_job_service
    backend = create_data_backend(request.app.state.settings)
    service = create_data_job_service(backend, request.app.state.qmt_service)
    request.app.state.data_job_service = service
    return service


def _get_data_maintenance_service(request: Request) -> DataMaintenanceService:
    if hasattr(request.app.state, "data_maintenance_service"):
        return request.app.state.data_maintenance_service
    backend = create_data_backend(request.app.state.settings)
    backend.initialize()
    service = DataMaintenanceService(
        backend.data_dir,
        repository=DataJobRepository(backend),
    )
    request.app.state.data_maintenance_service = service
    return service


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
