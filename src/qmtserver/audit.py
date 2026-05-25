from __future__ import annotations

import logging
from typing import Any

from qmtserver.config import Settings
from qmtserver.rpc.registry import RpcMethodSpec

AUDIT_LOGGER_NAME = "qmtserver.audit"


def audit_rpc_call(
    *,
    settings: Settings,
    spec: RpcMethodSpec | None,
    target: str,
    method: str,
    args: list[Any],
    kwargs: dict[str, Any],
    ok: bool,
    error_code: str | None,
    elapsed_ms: float,
    dry_run: bool | None = None,
) -> None:
    if not settings.audit_log:
        return

    level = spec.level if spec is not None else "unknown"
    args_summary = ""
    if settings.audit_log_args:
        args_summary = f" args={summarize_value(args)} kwargs={summarize_value(kwargs)}"
    dry_run_summary = "" if dry_run is None else f" dry_run={dry_run}"

    logging.getLogger(AUDIT_LOGGER_NAME).info(
        "rpc target=%s method=%s level=%s ok=%s error=%s elapsed_ms=%.3f%s%s",
        target,
        method,
        level,
        ok,
        error_code,
        elapsed_ms,
        dry_run_summary,
        args_summary,
    )


def summarize_value(value: Any) -> str:
    if value is None or isinstance(value, bool | int | float):
        return repr(value)
    if isinstance(value, str):
        return _summarize_string(value)
    if isinstance(value, list | tuple | set):
        items = list(value)
        preview = ", ".join(summarize_value(item) for item in items[:3])
        suffix = ", ..." if len(items) > 3 else ""
        return f"{type(value).__name__}(len={len(items)}, [{preview}{suffix}])"
    if isinstance(value, dict):
        if value.get("__type__") == "StockAccount":
            account_id = _mask_account(str(value.get("account_id", "")))
            account_type = value.get("account_type", "STOCK")
            return f"StockAccount(account_id={account_id}, account_type={account_type})"
        keys = list(value.keys())
        preview = ", ".join(str(key) for key in keys[:5])
        suffix = ", ..." if len(keys) > 5 else ""
        return f"dict(len={len(value)}, keys=[{preview}{suffix}])"
    if hasattr(value, "account_id"):
        return f"{type(value).__name__}(account_id={_mask_account(str(value.account_id))})"
    return type(value).__name__


def _summarize_string(value: str) -> str:
    if len(value) <= 16:
        return repr(value)
    return repr(f"{value[:8]}...{value[-4:]}")


def _mask_account(value: str) -> str:
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}****{value[-3:]}"
