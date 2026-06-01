from __future__ import annotations

from typing import Any

from qmtserver.market import MarketService


class XtDataBarReader:
    def __init__(self, qmt_service: Any) -> None:
        self.qmt_service = qmt_service

    def read_bars(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        market = MarketService(self.qmt_service)
        symbols = ",".join(str(symbol) for symbol in request.get("symbols", []))
        if request.get("kind") == "daily_bars":
            response = market.daily_bars(
                symbols=symbols,
                start=request.get("start") if isinstance(request.get("start"), str) else None,
                end=request.get("end") if isinstance(request.get("end"), str) else None,
                adjust=str(request.get("adjust", "none")),
            )
        else:
            response = market.intraday_bars(
                symbols=symbols,
                period=request.get("period") if isinstance(request.get("period"), str) else None,
                start=request.get("start") if isinstance(request.get("start"), str) else None,
                end=request.get("end") if isinstance(request.get("end"), str) else None,
                adjust=str(request.get("adjust", "none")),
            )
        if not response["ok"]:
            error = response["error"] or {"message": "market data read failed"}
            raise RuntimeError(str(error.get("message", "market data read failed")))
        return response["data"]["bars"]
