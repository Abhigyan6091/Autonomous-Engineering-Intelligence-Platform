"""
Projects API routes.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.database import get_db_session
from app.db.models import Project
from app.schemas.projects import ProjectCreate, ProjectResponse, ProjectUpdate

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> ProjectResponse:
    """Create a new project."""
    project = Project(
        name=data.name,
        description=data.description,
        configuration=data.configuration,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)

    logger.info("Project created", project_id=project.id, user=user_id)
    return ProjectResponse.from_orm_model(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> list[ProjectResponse]:
    """List all projects."""
    result = await db.execute(
        select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit)
    )
    projects = result.scalars().all()
    return [ProjectResponse.from_orm_model(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db_session),
    _user_id: str = Depends(get_current_user_id),
) -> ProjectResponse:
    """Get a single project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.from_orm_model(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> ProjectResponse:
    """Update a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.configuration is not None:
        project.configuration = data.configuration

    await db.flush()
    await db.refresh(project)
    logger.info("Project updated", project_id=project_id, user=user_id)
    return ProjectResponse.from_orm_model(project)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Delete a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await db.delete(project)
    logger.info("Project deleted", project_id=project_id, user=user_id)
