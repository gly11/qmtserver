from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from qmtserver.errors import QmtServerError
from qmtserver.rpc.registry import is_method_allowed
from qmtserver.rpc.serializers import convert_input, to_jsonable


@dataclass(frozen=True)
class RpcCall:
    target: str
    method: str
    args: list[Any]
    kwargs: dict[str, Any]


class RpcTargetProvider(Protocol):
    def get_target(self, target: str) -> Any: ...


class RpcDispatcher:
    def __init__(self, service: RpcTargetProvider) -> None:
        self.service = service

    def dispatch(self, call: RpcCall) -> dict[str, Any]:
        started_at = perf_counter()
        try:
            if not is_method_allowed(call.target, call.method):
                return _error_response(
                    call,
                    "METHOD_NOT_ALLOWED",
                    f"RPC method is not allowed: {call.target}.{call.method}",
                    started_at,
                )

            target = self.service.get_target(call.target)
            handler = getattr(target, call.method, None)
            if handler is None:
                return _error_response(
                    call,
                    "METHOD_NOT_FOUND",
                    f"RPC method does not exist: {call.target}.{call.method}",
                    started_at,
                )

            args = [convert_input(arg) for arg in call.args]
            kwargs = {key: convert_input(value) for key, value in call.kwargs.items()}
            result = handler(*args, **kwargs)
            return {
                "ok": True,
                "data": to_jsonable(result),
                "error": None,
                "meta": _meta(call, started_at),
            }
        except QmtServerError as exc:
            return _error_response(
                call,
                exc.code,
                str(exc),
                started_at,
            )
        except Exception as exc:
            return _error_response(
                call,
                type(exc).__name__,
                str(exc),
                started_at,
            )


def _error_response(
    call: RpcCall,
    code: str,
    message: str,
    started_at: float,
) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
        },
        "meta": _meta(call, started_at),
    }


def _meta(call: RpcCall, started_at: float) -> dict[str, Any]:
    return {
        "target": call.target,
        "method": call.method,
        "elapsed_ms": round((perf_counter() - started_at) * 1000, 3),
    }
