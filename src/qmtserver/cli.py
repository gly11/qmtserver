from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .miniqmt import QuoteCheckConfig, TraderCheckConfig, build_connectivity_report


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "check":
        return _run_check(args)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qmtserver")
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="verify MiniQMT connectivity")
    check.add_argument("--userdata", type=Path, help="MiniQMT userdata directory")
    check.add_argument("--account-id", help="fund account id")
    check.add_argument("--account-type", default="STOCK", help="account type, default: STOCK")
    check.add_argument("--session-id", type=int, help="xtquant session id")
    check.add_argument("--timeout-ms", type=int, default=5000, help="trader request timeout")
    check.add_argument("--quote-code", default="000001.SZ", help="symbol for quote check")
    check.add_argument("--quote-ip", default="", help="quote service ip, normally empty")
    check.add_argument("--quote-port", type=int, help="quote service port")
    check.add_argument("--skip-quote", action="store_true", help="skip quote connection check")
    check.add_argument("--json", action="store_true", help="print machine-readable JSON")

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
