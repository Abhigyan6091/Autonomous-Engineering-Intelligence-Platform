"""
Pydantic schemas for projects and repositories.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# PROJECT SCHEMAS
# =============================================================================

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    configuration: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, p: Any) -> "ProjectResponse":
        return cls(
            id=p.id,
            name=p.name,
            description=p.description,
            configuration=p.configuration,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )


# =============================================================================
# REPOSITORY SCHEMAS
# =============================================================================

class RepositoryCreate(BaseModel):
    project_id: str
    name: str = Field(..., min_length=1, max_length=255)
    url: str | None = None
    local_path: str | None = None
    branch: str = "main"
    language: str | None = None
    framework: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryResponse(BaseModel):
    id: str
    project_id: str
    name: str
    url: str | None
    local_path: str | None
    branch: str
    last_commit: str | None
    language: str | None
    framework: str | None
    indexed_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, r: Any) -> "RepositoryResponse":
        return cls(
            id=r.id,
            project_id=r.project_id,
            name=r.name,
            url=r.url,
            local_path=r.local_path,
            branch=r.branch,
            last_commit=r.last_commit,
            language=r.language,
            framework=r.framework,
            indexed_at=r.indexed_at,
            metadata=r.metadata_,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
