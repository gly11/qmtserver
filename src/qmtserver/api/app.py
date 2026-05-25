from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from qmtserver.api.routes_health import router as health_router
from qmtserver.api.routes_qmt import router as qmt_router
from qmtserver.api.routes_rpc import router as rpc_router
from qmtserver.config import Settings, load_settings
from qmtserver.services import QmtService


def create_app(settings: Settings | None = None, *, connect_on_startup: bool = True) -> FastAPI:
    app_settings = settings or load_settings()
    service = QmtService(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.qmt_service = service
        app.state.settings = app_settings
        if connect_on_startup and app_settings.auto_connect and app_settings.connect_on_startup:
            service.connect()
        try:
            yield
        finally:
            service.shutdown()

    app = FastAPI(
        title="qmtserver",
        version="0.1.0",
        description="Local MiniQMT readonly RPC gateway.",
        lifespan=lifespan,
    )
    app.state.qmt_service = service
    app.state.settings = app_settings
    app.include_router(health_router)
    app.include_router(qmt_router)
    app.include_router(rpc_router)
    return app
