"""
Test execution and coverage inspection tools.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool


class RunTestsInput(BaseModel):
    test_path: str = Field("tests", description="Test directory or file to run")
    filter_expr: str | None = Field(None, description="Pytest -k keyword filter expression")


class TestCaseResult(BaseModel):
    nodeid: str
    outcome: str  # passed | failed | error | skipped
    duration_sec: float
    error_message: str | None = None


class RunTestsOutput(BaseModel):
    total_tests: int
    passed: int
    failed: int
    errors: int
    output: str
    results: list[TestCaseResult]


class RunTestsTool(BaseTool[RunTestsInput, RunTestsOutput]):
    name = "run_tests"
    description = "Run pytest suite inside the sandbox environment."
    category = "test"
    risk_level = "medium"
    required_permissions = ["execute:sandbox"]
    input_schema = RunTestsInput
    output_schema = RunTestsOutput

    async def execute(self, params: RunTestsInput, context: dict[str, Any] | None = None) -> RunTestsOutput:
        workspace_path = context.get("workspace_path", ".") if context else "."
        target = Path(workspace_path) / params.test_path

        cmd = ["pytest", str(target), "-v", "--tb=short"]
        if params.filter_expr:
            cmd.extend(["-k", params.filter_expr])

        try:
            res = subprocess.run(cmd, cwd=workspace_path, capture_output=True, text=True, timeout=params.timeout_seconds if hasattr(params, 'timeout_seconds') else 30)
            output_text = res.stdout + res.stderr
            failed_count = output_text.count(" FAILED ")
            passed_count = output_text.count(" PASSED ")
            return RunTestsOutput(
                total_tests=failed_count + passed_count,
                passed=passed_count,
                failed=failed_count,
                errors=0 if res.returncode == 0 else 1,
                output=output_text[:10000],
                results=[],
            )
        except Exception as exc:
            return RunTestsOutput(
                total_tests=0,
                passed=0,
                failed=0,
                errors=1,
                output=f"Test runner error: {exc}",
                results=[],
            )
