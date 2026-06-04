from __future__ import annotations

import hashlib
import json
from typing import Any

from qmtserver.errors import QmtInvalidMarketRequestError

ALL_A_SECTOR = "\u6caa\u6df1A\u80a1"
SUPPORTED_EXCHANGES = {"SH", "SZ", "BJ"}


def canonicalize_download_request(request: dict[str, Any], qmt_service: Any) -> dict[str, Any]:
    symbols = _symbols(request.get("symbols"))
    universe = _text(request.get("universe"))
    exchange = _exchange(request.get("exchange"))
    if _text(request.get("exchange")) and exchange is None:
        raise QmtInvalidMarketRequestError(
            f"unsupported exchange: {request.get('exchange')}; expected one of BJ, SH, SZ"
        )
    if universe:
        resolved = resolve_universe(qmt_service, universe=universe, exchange=exchange)
        symbols = _unique([*symbols, *resolved])
    else:
        resolved = symbols
    if not symbols:
        raise QmtInvalidMarketRequestError("symbols or universe must include at least one symbol")
    canonical = dict(request)
    canonical["symbols"] = symbols
    canonical["resolved_symbols"] = resolved
    canonical["symbol_count"] = len(symbols)
    canonical["universe_hash"] = universe_hash(
        universe=universe,
        exchange=exchange,
        symbols=symbols,
    )
    if universe:
        canonical["universe"] = universe
    if exchange:
        canonical["exchange"] = exchange
    return canonical


def resolve_universe(qmt_service: Any, *, universe: str, exchange: str | None = None) -> list[str]:
    xtdata = qmt_service.get_target("xtdata")
    sector = ALL_A_SECTOR if universe == "all_a" else universe
    symbols = _symbols(xtdata.get_stock_list_in_sector(sector))
    if exchange:
        suffix = f".{exchange}"
        symbols = [symbol for symbol in symbols if symbol.endswith(suffix)]
    return _unique(symbols)


def universe_hash(*, universe: str, exchange: str | None, symbols: list[str]) -> str:
    payload = {
        "universe": universe,
        "exchange": exchange,
        "symbols": symbols,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _symbols(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return _unique(str(symbol).strip() for symbol in value if str(symbol).strip())


def _unique(symbols: Any) -> list[str]:
    seen = set()
    result = []
    for symbol in symbols:
        text = str(symbol).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _exchange(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().upper()
    return text if text in SUPPORTED_EXCHANGES else None
