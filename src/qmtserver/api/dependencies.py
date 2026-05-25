from __future__ import annotations

from fastapi import Request

from qmtserver.security import authenticate_request
from qmtserver.services import QmtService


def get_qmt_service(request: Request) -> QmtService:
    authenticate_request(request)
    return request.app.state.qmt_service
