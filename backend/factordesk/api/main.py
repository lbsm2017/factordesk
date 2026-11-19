"""FastAPI application factory (dashboard spec DB1).

``create_app(deps)`` builds the app from injected collaborators; ``create_dev_app`` is the
uvicorn factory for ``factordesk serve --dev`` and wires the real data layer. There is no CORS
middleware: development goes through the Vite proxy (``/api`` to ``http://127.0.0.1:8000``)
and production is same-origin.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from factordesk.api.deps import AppDeps, default_deps
from factordesk.api.errors import install_error_handlers
from factordesk.api.routes_factors import router as factors_router
from factordesk.api.routes_portfolio import router as portfolio_router
from factordesk.api.routes_report import router as report_router
from factordesk.api.routes_upload import UploadSizeLimit
from factordesk.api.routes_upload import router as upload_router
from factordesk.api.runtime import Runtime
from factordesk.api.service import ReportService
from factordesk.api.static import install_static
from factordesk.report.schema import SCHEMA_VERSION


def create_app(deps: AppDeps) -> FastAPI:
    """Build the API around ``deps``. Reads no disk and no network."""
    app = FastAPI(
        title="factordesk",
        summary="Local Fama-French 5-factor analysis API.",
        version=SCHEMA_VERSION,
    )
    runtime = Runtime(deps)
    app.state.runtime = runtime
    app.state.report_service = ReportService(runtime)
    install_error_handlers(app)
    app.add_middleware(UploadSizeLimit)
    app.include_router(factors_router)
    app.include_router(portfolio_router)
    app.include_router(upload_router)  # before /api/report/{ticker}
    app.include_router(report_router)
    if deps.static_dir is not None:
        install_static(app, deps.static_dir)  # last: its catch-all must not shadow the API
    return app


def create_dev_app() -> FastAPI:
    """Uvicorn factory (API only) with the real providers and the configured data directory."""
    if not logging.getLogger().handlers:  # the reload worker is a fresh process
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    logging.getLogger("factordesk").setLevel(logging.INFO)
    return create_app(default_deps(None))
