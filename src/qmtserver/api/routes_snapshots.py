from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.errors import QmtSnapshotNotFoundError
from qmtserver.services import QmtService
from qmtserver.snapshots import SnapshotService

router = APIRouter(prefix="/snapshots", tags=["snapshots"])
QmtServiceDep = Annotated[QmtService, Depends(get_qmt_service)]


class SnapshotCreateRequest(BaseModel):
    kind: str
    symbols: list[str] = Field(default_factory=list)
    start: str | None = None
    end: str | None = None
    adjust: str = "none"
    period: str | None = None
    format: str = "csv"


@router.post("")
def create_snapshot(request: SnapshotCreateRequest, service: QmtServiceDep) -> dict[str, object]:
    return _snapshot_service(service).create(request.model_dump())


@router.get("")
def list_snapshots(service: QmtServiceDep) -> dict[str, object]:
    return _snapshot_service(service).list_snapshots()


@router.get("/{snapshot_id}/manifest")
def get_manifest(snapshot_id: str, service: QmtServiceDep) -> dict[str, object]:
    try:
        return _snapshot_service(service).manifest(snapshot_id)
    except QmtSnapshotNotFoundError as exc:
        return _error(exc.code, str(exc))


@router.get("/{snapshot_id}/download", response_model=None)
def download_snapshot(snapshot_id: str, service: QmtServiceDep) -> FileResponse | dict[str, object]:
    try:
        path = _snapshot_service(service).download_path(snapshot_id)
    except QmtSnapshotNotFoundError as exc:
        return _error(exc.code, str(exc))
    return FileResponse(path, media_type="text/csv", filename=path.name)


def _snapshot_service(service: QmtService) -> SnapshotService:
    return SnapshotService(service, root=service.settings.snapshot_dir)


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}, "meta": {}}
