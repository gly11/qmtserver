from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from qmtserver.miniqmt import (
    MiniQmtCallback,
    TraderCheckConfig,
    _format_exception,
    _make_session_id,
    _to_plain,
    check_xtquant_import,
    load_trader_classes,
)


def build_trader_diagnostics(config: TraderCheckConfig) -> dict[str, Any]:
    userdata = config.userdata.expanduser().resolve()
    steps: list[dict[str, Any]] = []
    hints: list[str] = []
    report: dict[str, Any] = {
        "ok": False,
        "userdata": {
            "configured": True,
            "exists": userdata.exists(),
            "name": userdata.name,
        },
        "account": {
            "configured": bool(config.account_id),
            "account_id": _mask_account(config.account_id),
            "account_type": config.account_type,
        },
        "session_id": config.session_id,
        "timeout_ms": config.timeout_ms,
        "connect_result": None,
        "steps": steps,
        "hints": hints,
    }

    xtquant = check_xtquant_import()
    report["xtquant"] = {
        "ok": xtquant.get("ok", False),
        "version": xtquant.get("version"),
    }
    _add_step(steps, "xtquant_import", bool(xtquant.get("ok")), xtquant.get("error"))
    if not xtquant.get("ok"):
        hints.append("Install xtquant or use uv sync --extra xtquant on this Windows host.")
        return report

    if not userdata.exists():
        _add_step(steps, "userdata_path", False, "userdata path does not exist")
        hints.append("Check QMT_USERDATA or pass the MiniQMT userdata_mini directory explicitly.")
        return report
    _add_step(steps, "userdata_path", True, userdata.name)

    trader = None
    started = False
    callback = MiniQmtCallback()
    try:
        XtQuantTrader, StockAccount = load_trader_classes()
        _add_step(steps, "trader_classes", True, "loaded")

        session_id = config.session_id or _make_session_id()
        report["session_id"] = session_id
        trader = XtQuantTrader(str(userdata), session_id, callback)
        trader.set_timeout(config.timeout_ms)
        trader.start()
        started = True
        _add_step(steps, "trader_start", True, "started")

        connect_result = trader.connect()
        report["connect_result"] = connect_result
        connected = connect_result == 0
        _add_step(steps, "trader_connect", connected, f"connect_result={connect_result}")
        if not connected:
            hints.extend(_trader_connect_hints(connect_result))
            return report

        _run_trader_readonly_checks(
            steps=steps,
            hints=hints,
            report=report,
            trader=trader,
            StockAccount=StockAccount,
            config=config,
        )
        report["ok"] = all(bool(step.get("ok")) for step in steps)
        return report
    except Exception as exc:
        _add_step(steps, "trader_diagnostics", False, _redact_text(exc, userdata, config))
        hints.append("Check MiniQMT login state, userdata path, xtquant version, and timeout.")
        return report
    finally:
        if trader is not None and started:
            with contextlib.suppress(Exception):
                trader.stop()


def _run_trader_readonly_checks(
    *,
    steps: list[dict[str, Any]],
    hints: list[str],
    report: dict[str, Any],
    trader: Any,
    StockAccount: type[Any],
    config: TraderCheckConfig,
) -> None:
    try:
        status = trader.query_account_status()
        plain_status = _to_plain(status)
        count = len(plain_status) if isinstance(plain_status, list) else 0
        _add_step(steps, "query_account_status", True, f"rows={count}")
    except Exception as exc:
        _add_step(steps, "query_account_status", False, _format_exception(exc))
        hints.append("Trader connected but account status query failed; check MiniQMT login state.")

    if not config.account_id:
        hints.append("Set QMT_ACCOUNT_ID or pass --account-id to validate account subscribe/asset.")
        return

    try:
        account = StockAccount(config.account_id, config.account_type)
        _add_step(steps, "stock_account", True, "constructed")
        subscribe_result = _to_plain(trader.subscribe(account))
        report["subscribe_result"] = subscribe_result
        _add_step(steps, "account_subscribe", subscribe_result == 0, f"result={subscribe_result}")
        if subscribe_result != 0:
            hints.append("Account subscribe failed; verify account id and account type in MiniQMT.")
            return
        asset = _to_plain(trader.query_stock_asset(account))
        report["asset_present"] = asset is not None
        _add_step(steps, "query_stock_asset", asset is not None, "asset returned")
    except Exception as exc:
        _add_step(steps, "account_readonly", False, _format_exception(exc))
        hints.append(
            "Account readonly query failed; verify account id, account type, and login state."
        )


def _add_step(
    steps: list[dict[str, Any]],
    name: str,
    ok: bool,
    detail: Any = None,
) -> None:
    steps.append({"name": name, "ok": ok, "detail": detail})


def _trader_connect_hints(connect_result: Any) -> list[str]:
    if connect_result == -1:
        return [
            "MiniQMT may not be started or logged in.",
            "Verify QMT_USERDATA points to userdata_mini for the running MiniQMT instance.",
            "Try a larger --timeout-ms or a new --session-id if the trader session is stale.",
        ]
    return [
        "Trader connect did not return 0; check MiniQMT login state and xtquant compatibility.",
    ]


def _mask_account(account_id: str | None) -> str | None:
    if not account_id:
        return None
    if len(account_id) <= 6:
        return "***"
    return f"{account_id[:3]}****{account_id[-3:]}"


def _redact_text(exc: Exception, userdata: Path, config: TraderCheckConfig) -> str:
    text = _format_exception(exc).replace(str(userdata), "<userdata>")
    if config.account_id:
        text = text.replace(config.account_id, _mask_account(config.account_id) or "***")
    return text
