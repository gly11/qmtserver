from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from qmtserver.audit import audit_rpc_call, audit_trade_call
from qmtserver.config import Settings
from qmtserver.errors import QmtServerError, QmtTradingDisabledError
from qmtserver.rpc.registry import get_method_spec
from qmtserver.rpc.serializers import convert_input, to_jsonable
from qmtserver.trading import prepare_trading_call


@dataclass(frozen=True)
class RpcCall:
    target: str
    method: str
    args: list[Any]
    kwargs: dict[str, Any]
    request_id: str | None = None
    api_version: str | None = None


class RpcTargetProvider(Protocol):
    settings: Settings

    def get_target(self, target: str) -> Any: ...


class RpcDispatcher:
    def __init__(self, service: RpcTargetProvider) -> None:
        self.service = service

    def dispatch(self, call: RpcCall) -> dict[str, Any]:
        started_at = perf_counter()
        spec = get_method_spec(call.target, call.method)
        result: dict[str, Any]
        dry_run: bool | None = None
        trading_details: dict[str, object] | None = None
        real_trading_call = False

        try:
            if spec is None:
                result = _error_response(
                    call,
                    "METHOD_NOT_ALLOWED",
                    f"RPC method is not allowed: {call.target}.{call.method}",
                    started_at,
                )
                return result

            if spec.level == "trading" and not self.service.settings.enable_trading:
                raise QmtTradingDisabledError("Trading RPC methods are disabled")

            if not spec.enabled:
                result = _error_response(
                    call,
                    "METHOD_NOT_ALLOWED",
                    f"RPC method is not allowed: {call.target}.{call.method}",
                    started_at,
                    spec.level,
                )
                return result

            if spec.level == "trading":
                trading_plan = prepare_trading_call(
                    self.service.settings,
                    call,
                    getattr(self.service, "daily_trading_limits", None),
                )
                dry_run = trading_plan.dry_run
                trading_details = trading_plan.details
                if trading_plan.dry_run:
                    result = {
                        "ok": True,
                        "data": trading_plan.data,
                        "error": None,
                        "meta": _meta(call, started_at, spec.level),
                    }
                    return result
                kwargs_for_handler = trading_plan.kwargs
            else:
                kwargs_for_handler = call.kwargs

            target = self.service.get_target(call.target)
            handler = getattr(target, call.method, None)
            if handler is None:
                result = _error_response(
                    call,
                    "METHOD_NOT_FOUND",
                    f"RPC method does not exist: {call.target}.{call.method}",
                    started_at,
                    spec.level,
                )
                return result

            args = [convert_input(arg) for arg in call.args]
            kwargs = {key: convert_input(value) for key, value in kwargs_for_handler.items()}
            real_trading_call = spec.level == "trading"
            handler_result = handler(*args, **kwargs)
            if real_trading_call and trading_details is not None:
                daily_limits = getattr(self.service, "daily_trading_limits", None)
                if daily_limits is not None:
                    daily_limits.record_order(trading_details)
            result = {
                "ok": True,
                "data": to_jsonable(handler_result),
                "error": None,
                "meta": _meta(call, started_at, spec.level),
            }
            return result
        except QmtServerError as exc:
            result = _error_response(
                call,
                exc.code,
                str(exc),
                started_at,
                spec.level if spec is not None else None,
            )
            return result
        except Exception as exc:
            result = _error_response(
                call,
                type(exc).__name__,
                str(exc),
                started_at,
                spec.level if spec is not None else None,
            )
            return result
        finally:
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            ok = "result" in locals() and bool(result.get("ok"))
            error = result.get("error") if "result" in locals() else None
            audit_rpc_call(
                settings=self.service.settings,
                spec=spec,
                target=call.target,
                method=call.method,
                args=call.args,
                kwargs=call.kwargs,
                ok=ok,
                error_code=error.get("code") if isinstance(error, dict) else None,
                elapsed_ms=elapsed_ms,
                dry_run=dry_run,
            )
            if spec is not None and spec.level == "trading":
                audit_trade_call(
                    settings=self.service.settings,
                    target=call.target,
                    method=call.method,
                    details=trading_details,
                    dry_run=dry_run,
                    real_call=real_trading_call,
                    ok=ok,
                    error_code=error.get("code") if isinstance(error, dict) else None,
                )
            metrics = getattr(self.service, "metrics", None)
            if metrics is not None:
                metrics.record_rpc(ok=ok, elapsed_ms=elapsed_ms)


def _error_response(
    call: RpcCall,
    code: str,
    message: str,
    started_at: float,
    level: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
        },
        "meta": _meta(call, started_at, level),
    }


def _meta(call: RpcCall, started_at: float, level: str | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
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
