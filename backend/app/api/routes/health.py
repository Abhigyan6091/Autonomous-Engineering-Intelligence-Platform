"""
Health check routes — no authentication required.
"""
from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter()

_start_time = time.time()


class ComponentHealth(BaseModel):
    status: str  # healthy | degraded | unhealthy
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    uptime_seconds: float
    components: dict[str, ComponentHealth]


async def _check_database() -> ComponentHealth:
    """Check database connectivity."""
    try:
        from app.db.database import AsyncSessionLocal
        from sqlalchemy import text

        start = time.perf_counter()
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(status="healthy", latency_ms=round(latency_ms, 2))
    except Exception as exc:
        logger.warning("Database health check failed", error=str(exc))
        return ComponentHealth(status="unhealthy", detail=str(exc))


async def _check_redis() -> ComponentHealth:
    """Check Redis connectivity."""
    if settings.is_fake_redis:
        return ComponentHealth(status="healthy", detail="fakeredis (dev mode)")
    try:
        import redis.asyncio as aioredis

        start = time.perf_counter()
        client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(status="healthy", latency_ms=round(latency_ms, 2))
    except Exception as exc:
        logger.warning("Redis health check failed", error=str(exc))
        return ComponentHealth(status="unhealthy", detail=str(exc))


async def _check_qdrant() -> ComponentHealth:
    """Check Qdrant connectivity."""
    try:
        import httpx

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.QDRANT_URL}/readyz")
        latency_ms = (time.perf_counter() - start) * 1000
        if resp.status_code == 200:
            return ComponentHealth(status="healthy", latency_ms=round(latency_ms, 2))
        return ComponentHealth(status="degraded", detail=f"HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning("Qdrant health check failed", error=str(exc))
        return ComponentHealth(status="unhealthy", detail=str(exc))


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    Returns the health status of the API and all downstream dependencies.
    """
    db_health, redis_health, qdrant_health = (
        await _check_database(),
        await _check_redis(),
        await _check_qdrant(),
    )

    components = {
        "database": db_health,
        "redis": redis_health,
        "qdrant": qdrant_health,
    }

    # Overall status: healthy if all critical services are up
    critical_services = ["database"]
    overall = "healthy"
    for svc in critical_services:
        if components[svc].status == "unhealthy":
            overall = "unhealthy"
            break
        if components[svc].status == "degraded":
            overall = "degraded"

    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        uptime_seconds=round(time.time() - _start_time, 1),
        components=components,
    )


@router.get("/health/live", tags=["health"])
async def liveness() -> dict[str, Any]:
    """Kubernetes liveness probe — just confirms the process is alive."""
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, Any]:
    """Kubernetes readiness probe — confirms the app can serve traffic."""
    db = await _check_database()
    if db.status == "unhealthy":
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database not ready")
    return {"status": "ready"}
