from __future__ import annotations

from fastapi import APIRouter, Request

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.services import QmtService

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics(request: Request) -> dict[str, object]:
    service: QmtService = get_qmt_service(request)
    return request.app.state.metrics.snapshot(
        service=service,
        event_bus=request.app.state.event_bus,
        job_registry=request.app.state.job_registry,
    )
