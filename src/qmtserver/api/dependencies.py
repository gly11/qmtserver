from __future__ import annotations

from fastapi import Request

from qmtserver.services import QmtService


def get_qmt_service(request: Request) -> QmtService:
    return request.app.state.qmt_service
