"""
Pydantic schemas for investigations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


InvestigationMode = Literal["incident", "audit", "remediation"]
InvestigationStatus = Literal[
    "created", "planning", "running", "paused",
    "awaiting_approval", "completed", "failed", "budget_exceeded"
]
InvestigationPriority = Literal["low", "medium", "high", "critical"]


class TimeWindow(BaseModel):
    start: datetime
    end: datetime


class InvestigationCreate(BaseModel):
    project_id: str
    objective: str = Field(..., min_length=10, max_length=2000)
    mode: InvestigationMode = "incident"
    priority: InvestigationPriority = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("objective")
    @classmethod
    def sanitize_objective(cls, v: str) -> str:
        # Strip null bytes and other control characters
        return "".join(c for c in v if c.isprintable() or c in "\n\t")


class InvestigationUpdate(BaseModel):
    status: InvestigationStatus | None = None
    priority: InvestigationPriority | None = None
    metadata: dict[str, Any] | None = None


class InvestigationResponse(BaseModel):
    id: str
    project_id: str
    objective: str
    mode: InvestigationMode
    status: InvestigationStatus
    priority: InvestigationPriority
    created_by: str | None
    started_at: datetime | None
    completed_at: datetime | None
    confidence: float | None
    retry_count: int
    last_error: str | None
    budget_tokens_used: int
    budget_tokens_max: int
    budget_tool_calls_used: int
    budget_tool_calls_max: int
    langgraph_thread_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, inv: Any) -> "InvestigationResponse":
        return cls(
            id=inv.id,
            project_id=inv.project_id,
            objective=inv.objective,
            mode=inv.mode,
            status=inv.status,
            priority=inv.priority,
            created_by=inv.created_by,
            started_at=inv.started_at,
            completed_at=inv.completed_at,
            confidence=inv.confidence,
            retry_count=inv.retry_count,
            last_error=inv.last_error,
            budget_tokens_used=inv.budget_tokens_used,
            budget_tokens_max=inv.budget_tokens_max,
            budget_tool_calls_used=inv.budget_tool_calls_used,
            budget_tool_calls_max=inv.budget_tool_calls_max,
            langgraph_thread_id=inv.langgraph_thread_id,
            metadata=inv.metadata_,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
        )


class InvestigationListResponse(BaseModel):
    items: list[InvestigationResponse]
    total: int
    page: int
    page_size: int
