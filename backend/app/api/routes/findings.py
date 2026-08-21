"""
Findings API routes.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.database import get_db_session
from app.db.models import Finding

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/findings")
async def list_findings(
    investigation_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    """List findings, optionally filtered by investigation or severity."""
    q = select(Finding).order_by(Finding.confidence.desc())
    if investigation_id:
        q = q.where(Finding.investigation_id == investigation_id)
    if severity:
        q = q.where(Finding.severity == severity)

    result = await db.execute(q.limit(200))
    findings = result.scalars().all()
    return [
        {
            "id": f.id,
            "investigation_id": f.investigation_id,
            "claim": f.claim,
            "confidence": f.confidence,
            "confidence_tier": f.confidence_tier,
            "severity": f.severity,
            "category": f.category,
            "is_root_cause": f.is_root_cause,
            "evidence_count": len(f.evidence_ids),
            "created_at": f.created_at.isoformat(),
        }
        for f in findings
    ]
