from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.services import QmtService

router = APIRouter(prefix="/qmt", tags=["qmt"])
QmtServiceDep = Annotated[QmtService, Depends(get_qmt_service)]


@router.get("/status")
def status(service: QmtServiceDep) -> dict[str, object]:
    return service.status()


@router.post("/connect")
def connect(service: QmtServiceDep) -> dict[str, object]:
    return service.connect()


@router.post("/reconnect")
def reconnect(service: QmtServiceDep) -> dict[str, object]:
    return service.reconnect()


@router.post("/disconnect")
def disconnect(service: QmtServiceDep) -> dict[str, object]:
    return service.disconnect()
