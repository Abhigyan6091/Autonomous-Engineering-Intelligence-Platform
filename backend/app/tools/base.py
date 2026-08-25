"""
Base Tool definition and validation schemas for the AEIP platform.
Every tool must inherit from BaseTool and provide clear input/output schemas,
risk classifications, and permission requirements.
"""
from __future__ import annotations

import functools
import inspect
from abc import ABC, abstractmethod
from typing import Any, Generic, Literal, TypeVar
from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high", "critical"]

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ToolMetadata(BaseModel):
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Clear human-readable description of what the tool does")
    category: str = Field(..., description="Category (git, code, test, log, metrics, database, retrieval)")
    risk_level: RiskLevel = Field("low", description="Risk level (low, medium, high, critical)")
    required_permissions: list[str] = Field(default_factory=list, description="Required permissions to execute")
    timeout_seconds: int = Field(60, description="Execution timeout in seconds")
    requires_approval: bool = Field(False, description="Whether human approval is required before execution")


class ToolExecutionResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC, Generic[InputT, OutputT]):
    """Abstract Base Class for all AEIP Tools."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        Meter every tool invocation.

        Wrapping execute() here counts real tool calls, rather than inferring
        them from how much evidence an agent happened to return.
        """
        super().__init_subclass__(**kwargs)

        execute = cls.__dict__.get("execute")
        if execute is None or getattr(execute, "_aeip_metered", False):
            return
        if not inspect.iscoroutinefunction(execute):
            return

        @functools.wraps(execute)
        async def metered(self, params, context=None):  # type: ignore[no-untyped-def]
            from app.llm.usage import current_investigation_id, record_tool_call

            investigation_id = current_investigation_id.get()
            try:
                return await execute(self, params, context)
            finally:
                await record_tool_call(investigation_id, 1)

        metered._aeip_metered = True  # type: ignore[attr-defined]
        cls.execute = metered  # type: ignore[assignment]

    name: str
    description: str
    category: str
    risk_level: RiskLevel = "low"
    required_permissions: list[str] = []
    timeout_seconds: int = 60
    requires_approval: bool = False

    input_schema: type[InputT]
    output_schema: type[OutputT]

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            description=self.description,
            category=self.category,
            risk_level=self.risk_level,
            required_permissions=self.required_permissions,
            timeout_seconds=self.timeout_seconds,
            requires_approval=self.requires_approval,
        )

    @abstractmethod
    async def execute(self, params: InputT, context: dict[str, Any] | None = None) -> OutputT:
        """Execute the tool deterministically with validated input parameters."""
        pass
