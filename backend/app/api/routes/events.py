"""
Server-Sent Events (SSE) route for real-time investigation streaming.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.database import get_db_session
from app.db.models import AuditEvent, Investigation

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _generate_investigation_events(
    investigation_id: str,
    request: Request,
    last_event_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Generate SSE events for an investigation by polling the audit_events table.
    In production, this would use Redis Streams for lower latency.
    """
    from app.db.database import AsyncSessionLocal

    last_seen_id: str | None = last_event_id
    poll_interval = 1.0  # seconds

    # Verify investigation exists
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Investigation).where(Investigation.id == investigation_id)
        )
        if not result.scalar_one_or_none():
            yield {"data": json.dumps({"error": "Investigation not found"}), "event": "error"}
            return

    yield {
        "data": json.dumps({"message": "Connected to investigation stream"}),
        "event": "connected",
    }

    while True:
        # Check if client disconnected
        if await request.is_disconnected():
            logger.debug("SSE client disconnected", investigation_id=investigation_id)
            break

        async with AsyncSessionLocal() as db:
            # Fetch new audit events since last seen
            q = (
                select(AuditEvent)
                .where(AuditEvent.investigation_id == investigation_id)
                .order_by(AuditEvent.timestamp)
            )
            if last_seen_id:
                # This is a simplification; production would use cursor-based pagination
                q = q.where(AuditEvent.id > last_seen_id)

            result = await db.execute(q.limit(50))
            events = result.scalars().all()

            for event in events:
                last_seen_id = event.id
                yield {
                    "data": json.dumps({
                        "event_type": event.event_type,
                        "payload": event.payload,
                        "timestamp": event.timestamp.isoformat(),
                        "investigation_id": investigation_id,
                    }),
                    "event": event.event_type,
                    "id": event.id,
                }

            # Check if investigation is terminal
            inv_result = await db.execute(
                select(Investigation.status).where(Investigation.id == investigation_id)
            )
            inv_status = inv_result.scalar_one_or_none()
            if inv_status in ("completed", "failed", "budget_exceeded"):
                yield {
                    "data": json.dumps({
                        "event_type": "investigation.terminal",
                        "status": inv_status,
                    }),
                    "event": "investigation.terminal",
                }
                break

        await asyncio.sleep(poll_interval)


@router.get("/events/{investigation_id}/stream")
async def stream_investigation_events(
    investigation_id: str,
    request: Request,
    last_event_id: str | None = None,
) -> EventSourceResponse:
    """
    Server-Sent Events stream for real-time investigation progress.

    Connect to this endpoint to receive live updates as the investigation runs.
    Events are emitted for agent starts, tool calls, evidence additions, findings, etc.

    Automatically disconnects when the investigation reaches a terminal state.
    """
    return EventSourceResponse(
        _generate_investigation_events(investigation_id, request, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
