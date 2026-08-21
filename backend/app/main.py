"""
Autonomous Engineering Intelligence Platform — Backend Entry Point
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import approvals, events, findings, health, investigations, projects, repositories
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.observability import setup_observability, shutdown_observability
from app.db.database import create_db_and_tables

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    # Startup
    setup_logging()
    logger.info(
        "Starting AEIP backend",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )

    # Initialize observability
    setup_observability()

    # Create database tables (for dev; production uses migrations)
    if settings.APP_ENV == "development":
        await create_db_and_tables()
        logger.info("Database tables initialized")

    logger.info("AEIP backend ready", host="0.0.0.0", port=8000)

    yield

    # Shutdown
    logger.info("Shutting down AEIP backend")
    shutdown_observability()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Autonomous Engineering Intelligence Platform — "
            "AI-powered software reliability and engineering investigation platform."
        ),
        version=settings.APP_VERSION,
        docs_url=f"{settings.API_PREFIX}/docs" if settings.DEBUG else None,
        redoc_url=f"{settings.API_PREFIX}/redoc" if settings.DEBUG else None,
        openapi_url=f"{settings.API_PREFIX}/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ──────────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next: Any) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        return response

    # ── Exception handlers ─────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": "internal_error"},
        )

    # ── Routers ────────────────────────────────────────────────────────────
    # Health endpoints (no auth required)
    app.include_router(health.router, tags=["health"])

    # API v1 routes
    api_prefix = settings.API_PREFIX
    app.include_router(projects.router, prefix=api_prefix, tags=["projects"])
    app.include_router(repositories.router, prefix=api_prefix, tags=["repositories"])
    app.include_router(investigations.router, prefix=api_prefix, tags=["investigations"])
    app.include_router(findings.router, prefix=api_prefix, tags=["findings"])
    app.include_router(approvals.router, prefix=api_prefix, tags=["approvals"])
    app.include_router(events.router, prefix=api_prefix, tags=["events"])

    return app


app = create_application()
