"""
Approvals API routes — human approval workflow for consequential actions.
"""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.core.security import get_current_user_id
from app.db.database import get_db_session
from app.db.models import Approval

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _resume_graph(investigation_id: str | None, decision: str) -> None:
    """Resume the interrupted investigation; never let it fail the HTTP response."""
    if not investigation_id:
        return
    try:
        from app.graph.graph import resume_investigation_after_approval

        await resume_investigation_after_approval(investigation_id, decision)
    except Exception as exc:
        logger.error(
            "Failed to resume investigation after approval",
            investigation_id=investigation_id,
            decision=decision,
            error=str(exc),
            exc_info=True,
        )


class ApprovalDecision(BaseModel):
    """Body for approve/reject. The UI posts JSON, so notes must live here."""

    notes: str | None = None


@router.get("/approvals")
async def list_pending_approvals(
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    """List all pending approvals."""
    result = await db.execute(
        select(Approval)
        .where(Approval.status == "pending")
        .order_by(Approval.requested_at.desc())
    )
    approvals = result.scalars().all()
    return [
        {
            "id": a.id,
            "investigation_id": a.investigation_id,
            "action": a.action,
            "risk_level": a.risk_level,
            "description": a.description,
            "payload": a.payload,
            "requested_at": a.requested_at.isoformat(),
        }
        for a in approvals
    ]


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict:
    """Get approval details."""
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {
        "id": approval.id,
        "investigation_id": approval.investigation_id,
        "action": approval.action,
        "risk_level": approval.risk_level,
        "description": approval.description,
        "payload": approval.payload,
        "status": approval.status,
        "requested_at": approval.requested_at.isoformat(),
        "reviewed_at": approval.reviewed_at.isoformat() if approval.reviewed_at else None,
        "approved_by": approval.approved_by,
        "notes": approval.notes,
    }


@router.post("/approvals/{approval_id}/approve")
async def approve_action(
    approval_id: str,
    background_tasks: BackgroundTasks,
    body: ApprovalDecision | None = None,
    db: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Approve a pending action.
    This will resume the paused LangGraph investigation workflow.
    """
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Approval already {approval.status}"
        )

    approval.status = "approved"
    approval.approved_by = user_id
    approval.reviewed_at = datetime.now(UTC)
    approval.notes = body.notes if body else None

    logger.info(
        "Approval granted",
        approval_id=approval_id,
        investigation_id=approval.investigation_id,
        user=user_id,
    )

    # Resume the paused graph once the decision is committed.
    investigation_id = approval.investigation_id
    await db.commit()
    background_tasks.add_task(_resume_graph, investigation_id, "approved")

    return {"status": "approved", "approval_id": approval_id}


@router.post("/approvals/{approval_id}/reject")
async def reject_action(
    approval_id: str,
    background_tasks: BackgroundTasks,
    body: ApprovalDecision | None = None,
    db: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Reject a pending action.
    The investigation will be notified and may continue or terminate.
    """
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Approval already {approval.status}"
        )

    approval.status = "rejected"
    approval.approved_by = user_id
    approval.reviewed_at = datetime.now(UTC)
    approval.notes = body.notes if body else None

    logger.info(
        "Approval rejected",
        approval_id=approval_id,
        investigation_id=approval.investigation_id,
        user=user_id,
    )

    # Resume too: the graph routes a rejection to a clean stop.
    investigation_id = approval.investigation_id
    await db.commit()
    background_tasks.add_task(_resume_graph, investigation_id, "rejected")

    return {"status": "rejected", "approval_id": approval_id}
