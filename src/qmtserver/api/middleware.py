from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response

REQUEST_ID_HEADER = "X-Request-ID"
CallNext = Callable[[Request], Awaitable[Response]]


async def request_id_middleware(request: Request, call_next: CallNext) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
    request.state.request_id = request_id
    started_at = perf_counter()

    response = await call_next(request)
    elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
    response.headers[REQUEST_ID_HEADER] = request_id
    logging.getLogger("qmtserver.access").info(
        "request method=%s path=%s status=%s elapsed_ms=%.3f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
        extra={"request_id": request_id},
    )
    return response
