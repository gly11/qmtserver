from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from qmtserver.audit import audit_rpc_call, audit_trade_call
from qmtserver.config import Settings
from qmtserver.errors import QmtServerError, QmtTradingDisabledError
from qmtserver.rpc.registry import RpcMethodSpec, get_method_spec
from qmtserver.rpc.responses import error_response, success_response
from qmtserver.rpc.serializers import convert_input, to_jsonable
from qmtserver.rpc.transparent import transparent_method_decision
from qmtserver.rpc.types import RpcResponse
from qmtserver.trading import TradingDetails, TradingKwargs, prepare_trading_call


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


@dataclass
class DispatchState:
    started_at: float
    dry_run: bool | None = None
    trading_details: TradingDetails | None = None
    real_trading_call: bool = False


class RpcDispatcher:
    def __init__(self, service: RpcTargetProvider) -> None:
        self.service = service

    def dispatch(self, call: RpcCall) -> RpcResponse:
        started_at = perf_counter()
        spec = get_method_spec(call.target, call.method)
        state = DispatchState(started_at=started_at)
        result: RpcResponse

        try:
            if spec is None:
                decision = transparent_method_decision(
                    self.service.settings,
                    call.target,
                    call.method,
                )
                if decision.spec is None:
                    result = error_response(
                        call,
                        decision.error_code or "METHOD_NOT_ALLOWED",
                        decision.message
                        or f"RPC method is not allowed: {call.target}.{call.method}",
                        started_at,
                        decision.level,
                    )
                    return result
                spec = decision.spec

            if spec.level == "trading" and not self.service.settings.enable_trading:
                raise QmtTradingDisabledError("Trading RPC methods are disabled")

            if not spec.enabled:
                result = error_response(
                    call,
                    "METHOD_NOT_ALLOWED",
                    f"RPC method is not allowed: {call.target}.{call.method}",
                    started_at,
                    spec.level,
                )
                return result

            if spec.level == "trading":
                result = self._dispatch_trading(call, state)
            else:
                result = self._dispatch_method(call, spec.level, call.kwargs, state)
            return result
        except QmtServerError as exc:
            result = error_response(
                call,
                exc.code,
                str(exc),
                started_at,
                spec.level if spec is not None else None,
            )
            return result
        except Exception as exc:
            result = error_response(
                call,
                type(exc).__name__,
                str(exc),
                started_at,
                spec.level if spec is not None else None,
            )
            return result
        finally:
            response = result if "result" in locals() else None
            self._record_audit(call, spec, state, response)

    def _dispatch_trading(self, call: RpcCall, state: DispatchState) -> RpcResponse:
        trading_plan = prepare_trading_call(
            self.service.settings,
            call,
            getattr(self.service, "daily_trading_limits", None),
        )
        state.dry_run = trading_plan.dry_run
        state.trading_details = trading_plan.details
        if trading_plan.dry_run:
            return success_response(call, trading_plan.data, state.started_at, "trading")
        return self._dispatch_method(call, "trading", trading_plan.kwargs, state)

    def _dispatch_method(
        self,
        call: RpcCall,
        level: str,
        kwargs_for_handler: TradingKwargs,
        state: DispatchState,
    ) -> RpcResponse:
        handler = self._find_handler(call)
        if handler is None:
            return error_response(
                call,
                "METHOD_NOT_FOUND",
                f"RPC method does not exist: {call.target}.{call.method}",
                state.started_at,
                level,
            )

        args = [convert_input(arg) for arg in call.args]
        kwargs = {key: convert_input(value) for key, value in kwargs_for_handler.items()}
        state.real_trading_call = level == "trading"
        handler_result = handler(*args, **kwargs)
        self._record_order_if_needed(state)
        return success_response(call, to_jsonable(handler_result), state.started_at, level)

    def _find_handler(self, call: RpcCall) -> Callable[..., Any] | None:
        target = self.service.get_target(call.target)
        handler = getattr(target, call.method, None)
        return handler if callable(handler) else None

    def _record_order_if_needed(self, state: DispatchState) -> None:
        if not state.real_trading_call or state.trading_details is None:
            return
        daily_limits = getattr(self.service, "daily_trading_limits", None)
        if daily_limits is not None:
            daily_limits.record_order(state.trading_details)

    def _record_audit(
        self,
        call: RpcCall,
        spec: RpcMethodSpec | None,
        state: DispatchState,
        result: RpcResponse | None,
    ) -> None:
        elapsed_ms = round((perf_counter() - state.started_at) * 1000, 3)
        ok = bool(result["ok"]) if result is not None else False
        error = result["error"] if result is not None else None
        error_code = error.get("code") if isinstance(error, dict) else None
        audit_rpc_call(
            settings=self.service.settings,
            spec=spec,
            target=call.target,
            method=call.method,
            args=call.args,
            kwargs=call.kwargs,
            ok=ok,
            error_code=error_code,
            elapsed_ms=elapsed_ms,
            dry_run=state.dry_run,
        )
        if spec is not None and getattr(spec, "level", None) == "trading":
            audit_trade_call(
                settings=self.service.settings,
                target=call.target,
                method=call.method,
                details=state.trading_details,
                dry_run=state.dry_run,
                real_call=state.real_trading_call,
                ok=ok,
                error_code=error_code,
            )
        metrics = getattr(self.service, "metrics", None)
        if metrics is not None:
            metrics.record_rpc(ok=ok, elapsed_ms=elapsed_ms)
