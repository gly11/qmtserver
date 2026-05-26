from __future__ import annotations

from dataclasses import dataclass

from qmtserver.config import Settings
from qmtserver.rpc.registry import RpcMethodSpec

TRADING_METHOD_MARKERS = (
    "order",
    "cancel",
    "trade",
    "buy",
    "sell",
    "position_adjust",
)


@dataclass(frozen=True)
class TransparentMethodDecision:
    spec: RpcMethodSpec | None
    error_code: str | None = None
    message: str | None = None
    level: str | None = None


def transparent_method_decision(
    settings: Settings,
    target: str,
    method: str,
) -> TransparentMethodDecision:
    method_name = f"{target}.{method}"
    if not settings.transparent_rpc:
        return _reject(
            "METHOD_NOT_ALLOWED",
            f"RPC method is not allowed: {method_name}",
        )

    if target not in settings.transparent_rpc_allowed_targets():
        return _reject(
            "TRANSPARENT_TARGET_NOT_ALLOWED",
            f"Transparent RPC target is not allowed: {target}",
            level="transparent",
        )

    if target == "trader" and not settings.transparent_rpc_allow_trader:
        return _reject(
            "TRANSPARENT_TRADER_DENIED",
            "Transparent RPC for trader is disabled",
            level="transparent",
        )

    if not is_public_method_name(method):
        return _reject(
            "TRANSPARENT_METHOD_DENIED",
            f"Transparent RPC method is denied: {method_name}",
            level="transparent",
        )

    if is_trading_like_method(method):
        if not settings.transparent_rpc_allow_trading:
            return _reject(
                "TRANSPARENT_TRADING_DENIED",
                f"Transparent RPC trading-like method is denied: {method_name}",
                level="transparent",
            )
        return TransparentMethodDecision(RpcMethodSpec(target, method, "trading"))

    return TransparentMethodDecision(RpcMethodSpec(target, method, "transparent"))


def is_public_method_name(method: str) -> bool:
    return (
        bool(method) and method.isidentifier() and not method.startswith("_") and "__" not in method
    )


def is_trading_like_method(method: str) -> bool:
    lowered = method.lower()
    return any(marker in lowered for marker in TRADING_METHOD_MARKERS)


def _reject(
    code: str,
    message: str,
    *,
    level: str | None = None,
) -> TransparentMethodDecision:
    return TransparentMethodDecision(
        spec=None,
        error_code=code,
        message=message,
        level=level,
    )
