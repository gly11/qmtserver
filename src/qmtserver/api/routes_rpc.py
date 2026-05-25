from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from qmtserver.api.dependencies import get_qmt_service
from qmtserver.errors import API_VERSION
from qmtserver.rpc import RpcDispatcher, allowed_methods, method_specs
from qmtserver.rpc.dispatcher import RpcCall
from qmtserver.services import QmtService

router = APIRouter(prefix="/rpc", tags=["rpc"])
QmtServiceDep = Annotated[QmtService, Depends(get_qmt_service)]


class RpcRequest(BaseModel):
    target: str
    method: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


@router.get("/methods")
def methods(_service: QmtServiceDep) -> dict[str, object]:
    return {
        "ok": True,
        "methods": allowed_methods(),
        "specs": method_specs(),
    }


@router.post("")
def dispatch(
    request: RpcRequest,
    http_request: Request,
    service: QmtServiceDep,
) -> dict[str, object]:
    dispatcher = RpcDispatcher(service)
    request_id = getattr(http_request.state, "request_id", None)
    api_version = API_VERSION if http_request.url.path.startswith(f"/{API_VERSION}/") else None
    return dispatcher.dispatch(
        RpcCall(
            target=request.target,
            method=request.method,
            args=request.args,
            kwargs=request.kwargs,
            request_id=request_id,
            api_version=api_version,
        )
    )
