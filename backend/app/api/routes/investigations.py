"""
Investigations API routes — the primary API for creating and monitoring investigations.
"""
from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.database import get_db_session
from app.db.models import Evidence, Finding, Hypothesis, Investigation, Task
from app.schemas.investigations import (
    InvestigationCreate,
    InvestigationListResponse,
    InvestigationResponse,
    InvestigationUpdate,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _launch_investigation(investigation_id: str) -> None:
    """
    Background task: launch the LangGraph investigation workflow.
    This runs asynchronously after the investigation is created.
    """
    try:
        from app.graph.graph import run_investigation
        await run_investigation(investigation_id)
    except Exception as exc:
        logger.error(
            "Investigation execution failed",
            investigation_id=investigation_id,
            error=str(exc),
            exc_info=True,
        )
        # Update status to failed in database
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Investigation).where(Investigation.id == investigation_id)
            )
            inv = result.scalar_one_or_none()
            if inv:
                inv.status = "failed"
                inv.last_error = str(exc)
                await db.commit()


@router.post(
    "/investigations",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_investigation(
    data: InvestigationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> InvestigationResponse:
    """
    Create a new investigation and launch it in the background.

    The investigation will start immediately and progress can be monitored via:
    - GET /investigations/{id} for status polling
    - GET /events/{id}/stream for real-time SSE events
    """
    from app.db.models import Project
    # Verify project exists
    project_result = await db.execute(select(Project).where(Project.id == data.project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    thread_id = str(uuid.uuid4())
    investigation = Investigation(
        project_id=data.project_id,
        objective=data.objective,
        mode=data.mode,
        status="created",
        priority=data.priority,
        created_by=user_id,
        metadata_=data.metadata,
        langgraph_thread_id=thread_id,
    )
    db.add(investigation)
    await db.flush()
    await db.refresh(investigation)

    logger.info(
        "Investigation created",
        investigation_id=investigation.id,
        mode=investigation.mode,
        user=user_id,
    )

    # Launch the LangGraph workflow in the background
    background_tasks.add_task(_launch_investigation, investigation.id)

    return InvestigationResponse.from_orm_model(investigation)


@router.get("/investigations", response_model=InvestigationListResponse)
async def list_investigations(
    project_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    mode: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> InvestigationListResponse:
    """List investigations with optional filters."""
    from sqlalchemy import func

    q = select(Investigation).order_by(Investigation.created_at.desc())
    if project_id:
        q = q.where(Investigation.project_id == project_id)
    if status_filter:
        q = q.where(Investigation.status == status_filter)
    if mode:
        q = q.where(Investigation.mode == mode)

    # Count total
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginate
    skip = (page - 1) * page_size
    result = await db.execute(q.offset(skip).limit(page_size))
    items = [InvestigationResponse.from_orm_model(i) for i in result.scalars().all()]

    return InvestigationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> InvestigationResponse:
    """Get investigation by ID."""
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return InvestigationResponse.from_orm_model(inv)


@router.get("/investigations/{investigation_id}/tasks")
async def get_investigation_tasks(
    investigation_id: str,
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    """Get all tasks for an investigation."""
    result = await db.execute(
        select(Task)
        .where(Task.investigation_id == investigation_id)
        .order_by(Task.created_at)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "assigned_agent": t.assigned_agent,
            "description": t.description,
            "status": t.status,
            "retry_count": t.retry_count,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "error": t.error,
        }
        for t in tasks
    ]


@router.get("/investigations/{investigation_id}/hypotheses")
async def get_investigation_hypotheses(
    investigation_id: str,
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    """Get all hypotheses for an investigation."""
    result = await db.execute(
        select(Hypothesis)
        .where(Hypothesis.investigation_id == investigation_id)
        .order_by(Hypothesis.confidence.desc())
    )
    hypotheses = result.scalars().all()
    return [
        {
            "id": h.id,
            "statement": h.statement,
            "confidence": h.confidence,
            "confidence_tier": h.confidence_tier,
            "status": h.status,
            "supporting_evidence_count": len(h.supporting_evidence_ids),
            "contradicting_evidence_count": len(h.contradicting_evidence_ids),
            "critique_notes": h.critique_notes,
        }
        for h in hypotheses
    ]


@router.get("/investigations/{investigation_id}/evidence")
async def get_investigation_evidence(
    investigation_id: str,
    source_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    """Get evidence collected during an investigation."""
    q = select(Evidence).where(Evidence.investigation_id == investigation_id)
    if source_type:
        q = q.where(Evidence.source_type == source_type)
    result = await db.execute(q.order_by(Evidence.timestamp))
    evidence = result.scalars().all()
    return [
        {
            "id": e.id,
            "source_type": e.source_type,
            "source": e.source,
            "summary": e.summary,
            "quality_score": e.quality_score,
            "tool_execution_id": e.tool_execution_id,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in evidence
    ]


@router.get("/investigations/{investigation_id}/report")
async def get_investigation_report(
    investigation_id: str,
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict:
    """Get the final investigation report."""
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if inv.status not in ("completed", "budget_exceeded"):
        raise HTTPException(
            status_code=409,
            detail=f"Report not yet available. Investigation status: {inv.status}",
        )
    return inv.final_report or {"error": "Report generation failed"}
