"""
Stub agents for log, test, data (metrics), and research analysis.
Each follows the same interface: run(state) -> list[EvidenceItem].
"""
from __future__ import annotations

import uuid
import structlog

from app.graph.state import AgentState, EvidenceItem
from app.tools.logs.tools import SearchLogsTool
from app.tools.tests.tools import RunTestsTool
from app.tools.metrics.tools import QueryLatencyTool, QueryErrorRateTool
from app.tools.retrieval.tools import SearchDocumentationTool

logger = structlog.get_logger(__name__)


class LogAgent:
    """Analyzes application logs for errors, exceptions, and anomalies."""

    async def run(self, state: AgentState) -> list[EvidenceItem]:
        context = {"workspace_path": state.metadata.get("workspace_path", ".")}
        items: list[EvidenceItem] = []

        tool = SearchLogsTool()
        # Search for errors and exceptions
        for query in ["ERROR", "Exception", "500", "Traceback"]:
            result = await tool.execute(tool.input_schema(query=query), context=context)
            if result.entries:
                content = "\n".join(e.message for e in result.entries[:20])
                items.append(EvidenceItem(
                    id=str(uuid.uuid4()),
                    source_type="logs",
                    source=f"log_search:{query}",
                    content=content,
                    summary=f"Log search for '{query}' found {result.total_found} entries.",
                    quality_score=0.85,
                ))
        return items


class TestAgent:
    """Runs tests and analyzes test coverage gaps."""

    async def run(self, state: AgentState) -> list[EvidenceItem]:
        context = {"workspace_path": state.metadata.get("workspace_path", ".")}
        items: list[EvidenceItem] = []

        tool = RunTestsTool()
        result = await tool.execute(tool.input_schema(), context=context)
        items.append(EvidenceItem(
            id=str(uuid.uuid4()),
            source_type="test",
            source="pytest",
            content=result.output[:3000],
            summary=f"Tests: {result.passed} passed, {result.failed} failed, {result.errors} errors out of {result.total_tests} total.",
            quality_score=0.9 if result.failed == 0 else 0.95,
        ))
        return items


class DataAgent:
    """Analyzes latency, error rate, and resource utilization metrics."""

    async def run(self, state: AgentState) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        service = state.metadata.get("service_name", "api")
        endpoint = state.metadata.get("primary_endpoint", f"/api/{service}")

        # Query latency
        latency_tool = QueryLatencyTool()
        latency_result = await latency_tool.execute(latency_tool.input_schema(endpoint=endpoint))
        items.append(EvidenceItem(
            id=str(uuid.uuid4()),
            source_type="metrics",
            source=f"latency:{endpoint}",
            content=latency_result.model_dump_json(),
            summary=latency_result.summary,
            quality_score=0.9,
        ))

        # Query error rate
        error_tool = QueryErrorRateTool()
        error_result = await error_tool.execute(error_tool.input_schema(service=service))
        items.append(EvidenceItem(
            id=str(uuid.uuid4()),
            source_type="metrics",
            source=f"error_rate:{service}",
            content=error_result.model_dump_json(),
            summary=f"Service '{service}': error rate {error_result.error_rate_pct:.1f}% vs baseline {error_result.baseline_error_rate_pct:.1f}%.",
            quality_score=0.88,
        ))
        return items


class ResearchAgent:
    """Searches documentation, runbooks, and architectural knowledge."""

    async def run(self, state: AgentState) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        tool = SearchDocumentationTool()
        result = await tool.execute(tool.input_schema(query=state.objective[:200]))
        for doc in result.documents:
            items.append(EvidenceItem(
                id=str(uuid.uuid4()),
                source_type="docs",
                source=doc.source_uri,
                content=doc.content[:2000],
                summary=f"[{doc.title}] Relevance: {doc.relevance_score:.2f}",
                quality_score=doc.relevance_score,
            ))
        return items
