from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from qmtserver import __version__
from qmtserver.api.middleware import request_id_middleware
from qmtserver.api.routes_diagnostics import router as diagnostics_router
from qmtserver.api.routes_health import router as health_router
from qmtserver.api.routes_jobs import router as jobs_router
from qmtserver.api.routes_market import router as market_router
from qmtserver.api.routes_metrics import router as metrics_router
from qmtserver.api.routes_orders import router as orders_router
from qmtserver.api.routes_qmt import router as qmt_router
from qmtserver.api.routes_reference import router as reference_router
from qmtserver.api.routes_rpc import router as rpc_router
from qmtserver.api.routes_snapshots import router as snapshots_router
from qmtserver.api.routes_trader import router as trader_router
from qmtserver.api.routes_ws import router as ws_router
from qmtserver.config import Settings, load_settings
from qmtserver.events import EventBus
from qmtserver.jobs import JobRegistry
from qmtserver.observability import Metrics, configure_logging
from qmtserver.orders import OrderStore
from qmtserver.services import QmtService

API_PREFIX = "/v1"


def create_app(settings: Settings | None = None, *, connect_on_startup: bool = True) -> FastAPI:
    app_settings = settings or load_settings()
    configure_logging(app_settings)
    event_bus = EventBus(
        queue_size=app_settings.ws_client_queue_size,
        cache_size=app_settings.event_cache_size,
    )
    metrics = Metrics()
    job_registry = JobRegistry()
    order_store = OrderStore(max_records=app_settings.order_cache_size)
    service = QmtService(
        app_settings,
        event_bus=event_bus,
        metrics=metrics,
        order_store=order_store,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.qmt_service = service
        app.state.settings = app_settings
        app.state.event_bus = event_bus
        app.state.metrics = metrics
        app.state.job_registry = job_registry
        app.state.order_store = order_store
        if connect_on_startup and app_settings.auto_connect and app_settings.connect_on_startup:
            service.connect()
        try:
            yield
        finally:
            service.shutdown()

    app = FastAPI(
        title="qmtserver",
        version=__version__,
        description="Local MiniQMT gateway server.",
        lifespan=lifespan,
    )
    app.state.qmt_service = service
    app.state.settings = app_settings
    app.state.event_bus = event_bus
    app.state.metrics = metrics
    app.state.job_registry = job_registry
    app.state.order_store = order_store
    app.middleware("http")(request_id_middleware)
    app.include_router(health_router)
    app.include_router(qmt_router)
    app.include_router(market_router)
    app.include_router(jobs_router)
    app.include_router(diagnostics_router)
    app.include_router(reference_router)
    app.include_router(rpc_router)
    app.include_router(snapshots_router)
    app.include_router(trader_router)
    app.include_router(ws_router)
    app.include_router(metrics_router)
    app.include_router(orders_router)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(qmt_router, prefix=API_PREFIX)
    app.include_router(market_router, prefix=API_PREFIX)
    app.include_router(jobs_router, prefix=API_PREFIX)
    app.include_router(diagnostics_router, prefix=API_PREFIX)
    app.include_router(reference_router, prefix=API_PREFIX)
    app.include_router(rpc_router, prefix=API_PREFIX)
    app.include_router(snapshots_router, prefix=API_PREFIX)
    app.include_router(trader_router, prefix=API_PREFIX)
    app.include_router(ws_router, prefix=API_PREFIX)
    app.include_router(metrics_router, prefix=API_PREFIX)
    app.include_router(orders_router, prefix=API_PREFIX)
    return app
