from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .config import PROFILE_NAMES, load_settings, profile_env_file
from .data.cli import (
    build_data_maintenance_service,
    configure_data_parser,
    run_data,
)
from .miniqmt import (
    QuoteCheckConfig,
    TraderCheckConfig,
    build_connectivity_report,
)
from .trader.diagnostics import build_trader_diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "env":
        return _run_env(args)
    if args.command == "check":
        return _run_check(args)
    if args.command == "data":
        return _run_data(args)
    if args.command == "diagnose":
        return _run_diagnose(args)
    if args.command == "serve":
        return _run_serve(args)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qmtserver")
    subparsers = parser.add_subparsers(dest="command")

    env = subparsers.add_parser("env", help="manage local qmtserver env profiles")
    env_subparsers = env.add_subparsers(dest="env_action")
    env_use = env_subparsers.add_parser("use", help="copy .env.<profile> to .env")
    env_use.add_argument("profile", choices=sorted(PROFILE_NAMES), help="env profile to activate")
    env_use.add_argument("--no-backup", action="store_true", help="do not back up current .env")

    check = subparsers.add_parser("check", help="verify MiniQMT connectivity")
    _add_profile_args(check)
    check.add_argument("--userdata", type=Path, help="MiniQMT userdata_mini directory")
    check.add_argument("--account-id", help="fund account id")
    check.add_argument("--account-type", help="account type, default: STOCK")
    check.add_argument("--session-id", type=int, help="xtquant session id")
    check.add_argument("--timeout-ms", type=int, help="trader request timeout")
    check.add_argument("--quote-code", help="symbol for quote check")
    check.add_argument("--quote-ip", default="", help="quote service ip, normally empty")
    check.add_argument("--quote-port", type=int, help="quote service port")
    check.add_argument("--skip-quote", action="store_true", help="skip quote connection check")
    check.add_argument("--json", action="store_true", help="print machine-readable JSON")

    configure_data_parser(subparsers, _add_profile_args)

    diagnose = subparsers.add_parser("diagnose", help="diagnose qmtserver runtime targets")
    diagnose_subparsers = diagnose.add_subparsers(dest="diagnose_target")
    trader = diagnose_subparsers.add_parser("trader", help="diagnose readonly trader connection")
    _add_profile_args(trader)
    trader.add_argument("--userdata", type=Path, help="MiniQMT userdata_mini directory")
    trader.add_argument("--account-id", help="fund account id")
    trader.add_argument("--account-type", default=None, help="account type, default from settings")
    trader.add_argument("--session-id", type=int, help="xtquant session id")
    trader.add_argument("--timeout-ms", type=int, default=None, help="trader request timeout")
    trader.add_argument("--json", action="store_true", help="print machine-readable JSON")

    serve = subparsers.add_parser("serve", help="start readonly RPC gateway")
    _add_profile_args(serve)
    serve.add_argument("--userdata", type=Path, help="MiniQMT userdata_mini directory")
    serve.add_argument("--account-id", help="fund account id")
    serve.add_argument("--account-type", help="account type")
    serve.add_argument("--host", help="bind host")
    serve.add_argument("--port", type=int, help="bind port")
    serve.add_argument("--quote-code", help="default symbol for status checks")
    serve.add_argument("--reload", action="store_true", help="enable uvicorn reload")

    return parser


def _add_profile_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--profile", choices=sorted(PROFILE_NAMES), help="read .env.<profile>")
    group.add_argument(
        "--use-sim-account",
        action="store_const",
        dest="profile",
        const="sim",
        help="alias for --profile sim",
    )
    group.add_argument(
        "--use-live-account",
        action="store_const",
        dest="profile",
        const="live",
        help="alias for --profile live",
    )


def _run_env(args: argparse.Namespace) -> int:
    if args.env_action == "use":
        return _run_env_use(args)
    return 2


def _run_env_use(args: argparse.Namespace) -> int:
    source = profile_env_file(args.profile)
    target = Path(".env")
    backup = Path(".env.previous")
    if not source.exists():
        print(f"Profile file not found: {source}")
        return 1
    if target.exists() and not args.no_backup:
        shutil.copy2(target, backup)
    shutil.copy2(source, target)
    settings = _read_env_file(source)
    print(f"Switched qmtserver env profile: {args.profile}")
    print("Active file: .env")
    print(f"Source file: {source}")
    if not args.no_backup:
        print("Previous backup: .env.previous")
    print(f"userdata: {_display_path(settings.get('QMT_USERDATA', ''))}")
    print(f"userdata exists: {_path_exists(settings.get('QMT_USERDATA', ''))}")
    print(f"account id: {_secret_state(settings.get('QMT_ACCOUNT_ID', ''))}")
    print(f"api token: {_secret_state(settings.get('QMT_API_TOKEN', ''))}")
    print(f"enable trading: {settings.get('QMT_ENABLE_TRADING', '')}")
    print(f"trading dry run: {settings.get('QMT_TRADING_DRY_RUN', '')}")
    print(f"connect quote: {settings.get('QMT_CONNECT_QUOTE', '')}")
    print(f"connect trader: {settings.get('QMT_CONNECT_TRADER', '')}")
    return 0


def _run_check(args: argparse.Namespace) -> int:
    settings = load_settings(profile=args.profile) if args.profile else None
    quote = None
    if not args.skip_quote:
        quote = QuoteCheckConfig(
            code=args.quote_code or (settings.quote_code if settings else "000001.SZ"),
            ip=args.quote_ip,
            port=args.quote_port,
        )

    trader = None
    userdata = args.userdata or (settings.userdata if settings else None)
    if userdata:
        trader = TraderCheckConfig(
            userdata=userdata,
            account_id=args.account_id or (settings.account_id if settings else None),
            account_type=args.account_type or (settings.account_type if settings else "STOCK"),
            session_id=args.session_id,
            timeout_ms=args.timeout_ms or (settings.trader_timeout_ms if settings else 5000),
        )

    report = build_connectivity_report(quote=quote, trader=trader)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_summary(report)

    return 0 if report["ok"] else 1


def _run_data(args: argparse.Namespace) -> int:
    return run_data(args, service_builder=_build_data_maintenance_service)


def _build_data_maintenance_service(args: argparse.Namespace) -> Any:
    return build_data_maintenance_service(args)


def _run_diagnose(args: argparse.Namespace) -> int:
    if args.diagnose_target == "trader":
        return _run_diagnose_trader(args)
    return 2


def _run_diagnose_trader(args: argparse.Namespace) -> int:
    settings = load_settings(profile=args.profile)
    userdata = args.userdata or settings.userdata
    if userdata is None:
        report = {
            "ok": False,
            "userdata": {"configured": False, "exists": False, "name": None},
            "account": {
                "configured": bool(args.account_id or settings.account_id),
                "account_id": None,
                "account_type": args.account_type or settings.account_type,
            },
            "connect_result": None,
            "steps": [{"name": "userdata_path", "ok": False, "detail": "not configured"}],
            "hints": ["Set QMT_USERDATA or pass --userdata with the userdata_mini directory."],
        }
    else:
        report = build_trader_diagnostics(
            TraderCheckConfig(
                userdata=userdata,
                account_id=args.account_id or settings.account_id,
                account_type=args.account_type or settings.account_type,
                session_id=args.session_id,
                timeout_ms=args.timeout_ms or settings.trader_timeout_ms,
            )
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_trader_diagnostics(report)
    return 0 if report["ok"] else 1


def _print_trader_diagnostics(report: dict[str, Any]) -> None:
    print("qmtserver trader diagnostics")
    userdata = report.get("userdata") or {}
    print(f"- userdata: {userdata.get('name') or 'not configured'}")
    account = report.get("account") or {}
    if account.get("configured"):
        print(f"- account: {account.get('account_id')} ({account.get('account_type')})")
    connect_result = report.get("connect_result")
    if connect_result is not None:
        print(f"- connect result: {connect_result}")
    for step in report.get("steps") or []:
        status = "OK" if step.get("ok") else "FAILED"
        detail = step.get("detail")
        suffix = f" ({detail})" if detail else ""
        print(f"- {step.get('name')}: {status}{suffix}")
    hints = report.get("hints") or []
    if hints:
        print("Hints:")
        for hint in hints:
            print(f"- {hint}")
    print(f"- result: {'OK' if report.get('ok') else 'FAILED'}")


def _print_summary(report: dict[str, Any]) -> None:
    print("qmtserver connectivity check")
    print(f"- Python: {report['python']['implementation']} {report['python']['version']}")

    xtquant = report["xtquant"]
    if xtquant["ok"]:
        print(f"- xtquant: OK ({xtquant['path']})")
    else:
        print(f"- xtquant: FAILED ({xtquant['error']})")
        return

    quote = report.get("quote")
    if quote is not None:
        if quote["ok"]:
            print(f"- quote: OK ({quote['code']})")
        else:
            print(f"- quote: FAILED ({quote.get('error', 'not connected')})")

    trader = report.get("trader")
    if trader is not None:
        if trader["ok"]:
            print(f"- trader: OK (session {trader['session_id']})")
            if trader.get("subscribe_result") is not None:
                print(f"- account subscribe: {trader['subscribe_result']}")
            if trader.get("asset") is not None:
                print("- account asset: OK")
        else:
            print(f"- trader: FAILED ({trader.get('error', trader.get('connect_result'))})")

    print(f"- result: {'OK' if report['ok'] else 'FAILED'}")


def _run_serve(args: argparse.Namespace) -> int:
    _apply_serve_env(args)

    import uvicorn

    settings = load_settings(profile=args.profile)
    uvicorn.run(
        "qmtserver.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=args.reload,
    )
    return 0


def _apply_serve_env(args: argparse.Namespace) -> None:
    values = {
        "QMT_USERDATA": str(args.userdata) if args.userdata else None,
        "QMT_ACCOUNT_ID": args.account_id,
        "QMT_ACCOUNT_TYPE": args.account_type,
        "QMT_HOST": args.host,
        "QMT_PORT": str(args.port) if args.port is not None else None,
        "QMT_QUOTE_CODE": args.quote_code,
    }
    for key, value in values.items():
        if value is not None:
            os.environ[key] = value


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, raw = value.split("=", 1)
        values[key.strip()] = raw.strip()
    return values


def _secret_state(value: str) -> str:
    return "<set>" if value.strip().strip('"') else "<empty>"


def _display_path(value: str) -> str:
    text = value.strip().strip('"')
    if not text:
        return "<empty>"
    path = Path(text)
    parent = path.parent.name
    return f"{parent}\\{path.name}" if parent else path.name


def _path_exists(value: str) -> bool:
    text = value.strip().strip('"')
    return bool(text and Path(text).exists())
