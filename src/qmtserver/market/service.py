from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from qmtserver import __version__
from qmtserver.errors import QmtInvalidMarketRequestError, QmtServerError
from qmtserver.market.adapter import XtDataMarketAdapter
from qmtserver.market.models import (
    ADJUST_MODES,
    BAR_SCHEMA,
    CAPABILITIES_SCHEMA,
    SUPPORTED_PERIODS,
    MarketRequest,
)
from qmtserver.market.normalizers import normalize_daily_bars, normalize_intraday_bars
from qmtserver.miniqmt import check_xtquant_import


class MarketService:
    def __init__(self, qmt_service: Any) -> None:
        self.qmt_service = qmt_service
        self.adapter = XtDataMarketAdapter(qmt_service)

    def capabilities(self) -> dict[str, Any]:
        return {
            "ok": True,
            "data": {
                "schema_versions": [BAR_SCHEMA, CAPABILITIES_SCHEMA],
                "endpoints": [
                    "/v1/market/bars/daily",
                    "/v1/market/bars/intraday",
                    "/v1/market/capabilities",
                ],
                "periods": list(SUPPORTED_PERIODS),
                "adjust_modes": list(ADJUST_MODES),
                "methods": ["xtdata.get_market_data_ex"],
            },
            "error": None,
            "meta": self._meta(CAPABILITIES_SCHEMA, {}, 0),
        }

    def daily_bars(
        self,
        *,
        symbols: str | None,
        start: str | None,
        end: str | None,
        adjust: str,
    ) -> dict[str, Any]:
        try:
            request = self._request(symbols=symbols, start=start, end=end, adjust=adjust)
            raw = self.adapter.fetch_daily(request)
            bars = normalize_daily_bars(raw)
            return self._success(request, bars)
        except QmtServerError as exc:
            return self._error(exc, self._request_dict(symbols, start, end, adjust))
        except Exception as exc:
            return self._error_code(
                "MARKET_DATA_ERROR",
                f"{type(exc).__name__}: {exc}",
                self._request_dict(symbols, start, end, adjust),
            )

    def intraday_bars(
        self,
        *,
        symbols: str | None,
        period: str | None,
        start: str | None,
        end: str | None,
        adjust: str,
    ) -> dict[str, Any]:
        try:
            request = self._request(
                symbols=symbols,
                start=start,
                end=end,
                adjust=adjust,
                period=period,
            )
            raw = self.adapter.fetch_intraday(request)
            bars = normalize_intraday_bars(raw, period=request.period or "")
            return self._success(request, bars)
        except QmtServerError as exc:
            return self._error(exc, self._request_dict(symbols, start, end, adjust, period))
        except Exception as exc:
            return self._error_code(
                "MARKET_DATA_ERROR",
                f"{type(exc).__name__}: {exc}",
                self._request_dict(symbols, start, end, adjust, period),
            )

    def _request(
        self,
        *,
        symbols: str | None,
        start: str | None,
        end: str | None,
        adjust: str,
        period: str | None = None,
    ) -> MarketRequest:
        parsed_symbols = cast(
            list[str],
            [item.strip() for item in (symbols or "").split(",") if item.strip()],
        )
        if not parsed_symbols:
            raise QmtInvalidMarketRequestError("symbols must include at least one symbol")
        if adjust not in ADJUST_MODES:
            raise QmtInvalidMarketRequestError(f"unsupported adjust mode: {adjust}")
        if period is not None and period not in SUPPORTED_PERIODS:
            raise QmtInvalidMarketRequestError(f"unsupported period: {period}")
        return MarketRequest(parsed_symbols, start, end, adjust, period)

    def _success(self, request: MarketRequest, bars: list[Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "data": {"bars": bars},
            "error": None,
            "meta": self._meta(BAR_SCHEMA, request.as_dict(), len(bars)),
        }

    def _error(self, exc: QmtServerError, request: dict[str, Any]) -> dict[str, Any]:
        return self._error_code(exc.code, str(exc), request)

    def _error_code(self, code: str, message: str, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": False,
            "data": None,
            "error": {"code": code, "message": message},
            "meta": self._meta(BAR_SCHEMA, request, 0),
        }

    def _meta(self, schema: str, request: dict[str, Any], row_count: int) -> dict[str, Any]:
        xtquant = check_xtquant_import()
        return {
            "schema": schema,
            "request": request,
            "row_count": row_count,
            "generated_at": datetime.now(UTC).isoformat(),
            "qmtserver_version": __version__,
            "xtquant_version": xtquant.get("version") if xtquant["ok"] else None,
        }

    def _request_dict(
        self,
        symbols: str | None,
        start: str | None,
        end: str | None,
        adjust: str,
        period: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "symbols": [item.strip() for item in (symbols or "").split(",") if item.strip()],
            "start": start,
            "end": end,
            "adjust": adjust,
        }
        if period is not None:
            data["period"] = period
        return data
