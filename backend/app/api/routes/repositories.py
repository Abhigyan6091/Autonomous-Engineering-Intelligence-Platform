"""
Repositories API routes.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.database import get_db_session
from app.db.models import Project, Repository
from app.schemas.projects import RepositoryCreate, RepositoryResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/repositories",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_repository(
    data: RepositoryCreate,
    db: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> RepositoryResponse:
    """Register a repository with a project."""
    # Verify project exists
    project_result = await db.execute(select(Project).where(Project.id == data.project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    if not data.url and not data.local_path:
        raise HTTPException(
            status_code=400, detail="Either url or local_path must be provided"
        )

    repo = Repository(
        project_id=data.project_id,
        name=data.name,
        url=data.url,
        local_path=data.local_path,
        branch=data.branch,
        language=data.language,
        framework=data.framework,
        metadata_=data.metadata,
    )
    db.add(repo)
    await db.flush()
    await db.refresh(repo)
    logger.info("Repository registered", repo_id=repo.id, project_id=data.project_id)
    return RepositoryResponse.from_orm_model(repo)


@router.get("/repositories", response_model=list[RepositoryResponse])
async def list_repositories(
    project_id: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> list[RepositoryResponse]:
    """List repositories, optionally filtered by project."""
    q = select(Repository).order_by(Repository.created_at.desc())
    if project_id:
        q = q.where(Repository.project_id == project_id)
    result = await db.execute(q.offset(skip).limit(limit))
    return [RepositoryResponse.from_orm_model(r) for r in result.scalars().all()]


@router.get("/repositories/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: str,
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> RepositoryResponse:
    """Get a single repository."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepositoryResponse.from_orm_model(repo)
