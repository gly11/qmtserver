from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .config import load_settings
from .miniqmt import QuoteCheckConfig, TraderCheckConfig, build_connectivity_report


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "check":
        return _run_check(args)
    if args.command == "serve":
        return _run_serve(args)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qmtserver")
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="verify MiniQMT connectivity")
    check.add_argument("--userdata", type=Path, help="MiniQMT userdata_mini directory")
    check.add_argument("--account-id", help="fund account id")
    check.add_argument("--account-type", default="STOCK", help="account type, default: STOCK")
    check.add_argument("--session-id", type=int, help="xtquant session id")
    check.add_argument("--timeout-ms", type=int, default=5000, help="trader request timeout")
    check.add_argument("--quote-code", default="000001.SZ", help="symbol for quote check")
    check.add_argument("--quote-ip", default="", help="quote service ip, normally empty")
    check.add_argument("--quote-port", type=int, help="quote service port")
    check.add_argument("--skip-quote", action="store_true", help="skip quote connection check")
    check.add_argument("--json", action="store_true", help="print machine-readable JSON")

    serve = subparsers.add_parser("serve", help="start readonly RPC gateway")
    serve.add_argument("--userdata", type=Path, help="MiniQMT userdata_mini directory")
    serve.add_argument("--account-id", help="fund account id")
    serve.add_argument("--account-type", help="account type")
    serve.add_argument("--host", help="bind host")
    serve.add_argument("--port", type=int, help="bind port")
    serve.add_argument("--quote-code", help="default symbol for status checks")
    serve.add_argument("--reload", action="store_true", help="enable uvicorn reload")

    return parser


def _run_check(args: argparse.Namespace) -> int:
    quote = None
    if not args.skip_quote:
        quote = QuoteCheckConfig(code=args.quote_code, ip=args.quote_ip, port=args.quote_port)

    trader = None
    if args.userdata:
        trader = TraderCheckConfig(
            userdata=args.userdata,
            account_id=args.account_id,
            account_type=args.account_type,
            session_id=args.session_id,
            timeout_ms=args.timeout_ms,
        )

    report = build_connectivity_report(quote=quote, trader=trader)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_summary(report)

    return 0 if report["ok"] else 1


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

    settings = load_settings()
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
