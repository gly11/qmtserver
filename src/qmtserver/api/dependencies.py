from __future__ import annotations

from fastapi import Request

from qmtserver.market.subscription_service import MarketSubscriptionService
from qmtserver.security import authenticate_request
from qmtserver.services import QmtService


def get_qmt_service(request: Request) -> QmtService:
    authenticate_request(request)
    return request.app.state.qmt_service


def get_market_subscription_service(request: Request) -> MarketSubscriptionService:
    authenticate_request(request)
    return request.app.state.market_subscription_service
