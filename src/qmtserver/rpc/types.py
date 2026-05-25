from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class RpcError(TypedDict):
    code: str
    message: str


class RpcMeta(TypedDict):
    target: str
    method: str
    elapsed_ms: float
    request_id: NotRequired[str]
    version: NotRequired[str]
    level: NotRequired[str]


class RpcResponse(TypedDict):
    ok: bool
    data: Any
    error: RpcError | None
    meta: RpcMeta
