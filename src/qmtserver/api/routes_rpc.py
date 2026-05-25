from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from qmtserver.api.dependencies import get_qmt_service
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
    service: QmtServiceDep,
) -> dict[str, object]:
    dispatcher = RpcDispatcher(service)
    return dispatcher.dispatch(
        RpcCall(
            target=request.target,
            method=request.method,
            args=request.args,
            kwargs=request.kwargs,
        )
    )
