from __future__ import annotations

from typing import Any

RUNTIME_HEALTH_SCHEMA = "runtime.health.v1"


def build_runtime_health(
    qmt_status: dict[str, Any],
    *,
    subscription_service: Any | None = None,
) -> dict[str, Any]:
    subscriptions = _subscription_health(subscription_service)
    quote = _target_health(qmt_status, "quote")
    trader = _target_health(qmt_status, "trader")
    status = "ok"
    reasons: list[str] = []
    if quote["status"] != "connected":
        status = "degraded"
        reasons.append("quote_disconnected")
    if subscriptions["degraded"] or subscriptions["stale_callbacks"]:
        status = "degraded"
        if subscriptions["degraded"]:
            reasons.append("subscription_degraded")
        if subscriptions["stale_callbacks"]:
            reasons.append("subscription_callback_stale")
    return {
        "schema": RUNTIME_HEALTH_SCHEMA,
        "status": status,
        "reasons": reasons,
        "quote": quote,
        "trader": trader,
        "subscriptions": subscriptions,
    }


def _target_health(qmt_status: dict[str, Any], target: str) -> dict[str, Any]:
    data = qmt_status.get(target) or {}
    enabled = data.get("enabled", True)
    connected = bool(data.get("connected"))
    if connected:
        status = "connected"
    elif not enabled:
        status = "not_configured"
    else:
        status = "disconnected"
    return {
        "status": status,
        "connected": connected,
        "enabled": enabled,
    }


def _subscription_health(subscription_service: Any | None) -> dict[str, Any]:
    if subscription_service is None:
        return _empty_subscription_health()
    try:
        subscriptions = list(subscription_service.list_subscriptions())
    except Exception:
        return _empty_subscription_health()

    counts = _empty_subscription_health()
    counts["total"] = len(subscriptions)
    for subscription in subscriptions:
        data = _subscription_dict(subscription)
        status = str(data.get("status") or "")
        if status in {"active", "degraded", "stopped"}:
            counts[status] += 1
        if status == "active" and _is_stale(subscription_service, str(data.get("subscription_id"))):
            counts["stale_callbacks"] += 1
    return counts


def _empty_subscription_health() -> dict[str, int]:
    return {
        "total": 0,
        "active": 0,
        "degraded": 0,
        "stopped": 0,
        "stale_callbacks": 0,
    }


def _subscription_dict(subscription: Any) -> dict[str, Any]:
    if hasattr(subscription, "as_dict"):
        data = subscription.as_dict()
        return data if isinstance(data, dict) else {}
    return subscription if isinstance(subscription, dict) else {}


def _is_stale(subscription_service: Any, subscription_id: str) -> bool:
    if not subscription_id:
        return False
    try:
        diagnostics = subscription_service.diagnostics(subscription_id)
    except Exception:
        return False
    return bool(
        diagnostics.get("callback_count", 0) and diagnostics.get("is_callback_active") is False
    )
