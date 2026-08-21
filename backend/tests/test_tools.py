"""
Unit tests for deterministic platform tools.
"""
import pytest
import asyncio
from app.tools.filesystem.tools import ListFilesTool, ReadFileTool
from app.tools.code.tools import SearchCodeTool, RunStaticAnalysisTool
from app.tools.metrics.tools import QueryLatencyTool, QueryErrorRateTool
from app.tools.database.tools import ReadSchemaTool, ExecuteReadonlyQueryTool
from app.tools.retrieval.tools import SearchDocumentationTool


@pytest.mark.asyncio
async def test_list_files_tool():
    tool = ListFilesTool()
    res = await tool.execute(tool.input_schema(directory_path=".", recursive=False))
    assert res.total_count >= 0
    assert isinstance(res.files, list)


@pytest.mark.asyncio
async def test_read_file_tool():
    tool = ReadFileTool()
    res = await tool.execute(tool.input_schema(file_path="pyproject.toml", start_line=1, max_lines=10))
    # It will safely handle whether file is in current cwd or not
    assert res.file_path == "pyproject.toml"


@pytest.mark.asyncio
async def test_search_code_tool():
    tool = SearchCodeTool()
    res = await tool.execute(tool.input_schema(query="FastAPI", file_pattern="*.py"))
    assert isinstance(res.matches, list)


@pytest.mark.asyncio
async def test_static_analysis_tool():
    tool = RunStaticAnalysisTool()
    res = await tool.execute(tool.input_schema(target_path="app"))
    assert res.total_issues >= 0


@pytest.mark.asyncio
async def test_query_latency_tool():
    tool = QueryLatencyTool()
    res = await tool.execute(tool.input_schema(endpoint="/api/v1/checkout"))
    assert res.endpoint == "/api/v1/checkout"
    assert res.current_p95_ms > res.baseline_p95_ms
    assert len(res.datapoints) == 2


@pytest.mark.asyncio
async def test_query_error_rate_tool():
    tool = QueryErrorRateTool()
    res = await tool.execute(tool.input_schema(service="checkout-api"))
    assert res.service == "checkout-api"
    assert res.error_rate_pct > 0


@pytest.mark.asyncio
async def test_read_schema_tool():
    tool = ReadSchemaTool()
    res = await tool.execute(tool.input_schema())
    assert len(res.tables) >= 2
    table_names = [t.table_name for t in res.tables]
    assert "inventory_items" in table_names
    assert "orders" in table_names


@pytest.mark.asyncio
async def test_database_readonly_security_guardrail():
    tool = ExecuteReadonlyQueryTool()
    # Test valid query
    valid_res = await tool.execute(tool.input_schema(query="EXPLAIN SELECT * FROM inventory_items"))
    assert valid_res.error is None
    assert valid_res.row_count >= 1

    # Test blocked destructive query
    invalid_res = await tool.execute(tool.input_schema(query="DROP TABLE inventory_items;"))
    assert "Security Violation" in invalid_res.error


@pytest.mark.asyncio
async def test_search_documentation_tool():
    tool = SearchDocumentationTool()
    res = await tool.execute(tool.input_schema(query="checkout latency regression"))
    assert res.total_found >= 1
    assert "Checkout API Performance Runbook" in res.documents[0].title
