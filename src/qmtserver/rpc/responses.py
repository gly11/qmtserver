from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol

from qmtserver.rpc.types import RpcMeta, RpcResponse


class RpcCallFields(Protocol):
    target: str
    method: str
    request_id: str | None
    api_version: str | None


def success_response(
    call: RpcCallFields,
    data: Any,
    started_at: float,
    level: str | None = None,
) -> RpcResponse:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "meta": response_meta(call, started_at, level),
    }


def error_response(
    call: RpcCallFields,
    code: str,
    message: str,
    started_at: float,
    level: str | None = None,
) -> RpcResponse:
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
        },
        "meta": response_meta(call, started_at, level),
    }


def response_meta(call: RpcCallFields, started_at: float, level: str | None = None) -> RpcMeta:
    meta: RpcMeta = {
        "target": call.target,
        "method": call.method,
        "elapsed_ms": round((perf_counter() - started_at) * 1000, 3),
    }
    if call.request_id is not None:
        meta["request_id"] = call.request_id
    if call.api_version is not None:
        meta["version"] = call.api_version
    if level is not None:
        meta["level"] = level
    return meta
