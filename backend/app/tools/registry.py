"""
Tool Registry for AEIP platform.
Maintains a registry of all available tools, their schemas, permissions, and handlers.
"""
from __future__ import annotations

from typing import Any
import structlog
from app.tools.base import BaseTool, ToolMetadata

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """Central registry for all tools in the system."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            logger.warning("Overwriting existing registered tool", tool_name=tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool", tool_name=tool.name, category=tool.category, risk_level=tool.risk_level)

    def get_tool(self, name: str) -> BaseTool | None:
        """Retrieve a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[ToolMetadata]:
        """List metadata for all registered tools, optionally filtered by category."""
        tools = self._tools.values()
        if category:
            tools = [t for t in tools if t.category == category]
        return [t.metadata for t in tools]

    def get_all_tools(self) -> dict[str, BaseTool]:
        """Return dict of all registered tools."""
        return self._tools.copy()


# Global registry singleton
registry = ToolRegistry()
