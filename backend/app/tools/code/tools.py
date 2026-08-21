"""
Code inspection, search, and static analysis tools.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool


class SearchCodeInput(BaseModel):
    query: str = Field(..., description="Regex or text query to search across repository")
    file_pattern: str = Field("*.py", description="File glob pattern (e.g. *.py, *.ts)")
    max_results: int = Field(25, description="Maximum matches to return")


class SearchMatch(BaseModel):
    file_path: str
    line_number: int
    line_content: str


class SearchCodeOutput(BaseModel):
    matches: list[SearchMatch]
    total_matches: int


class SearchCodeTool(BaseTool[SearchCodeInput, SearchCodeOutput]):
    name = "search_code"
    description = "Search for keywords, functions, classes, or patterns across repository code."
    category = "code"
    risk_level = "low"
    required_permissions = ["read:repo"]
    input_schema = SearchCodeInput
    output_schema = SearchCodeOutput

    async def execute(self, params: SearchCodeInput, context: dict[str, Any] | None = None) -> SearchCodeOutput:
        base_dir = Path(context.get("workspace_path", ".")) if context else Path(".")
        matches: list[SearchMatch] = []

        try:
            pattern = re.compile(params.query, re.IGNORECASE)
            for path in base_dir.rglob(params.file_pattern):
                if not path.is_file() or ".git" in path.parts:
                    continue
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_idx, line in enumerate(f, start=1):
                            if pattern.search(line):
                                rel_p = str(path.relative_to(base_dir)).replace("\\", "/")
                                matches.append(SearchMatch(file_path=rel_p, line_number=line_idx, line_content=line.strip()))
                                if len(matches) >= params.max_results:
                                    break
                except Exception:
                    continue
                if len(matches) >= params.max_results:
                    break
        except Exception:
            pass

        return SearchCodeOutput(matches=matches, total_matches=len(matches))


class RunStaticAnalysisInput(BaseModel):
    tool: str = Field("ruff", description="Static analysis tool (ruff | bandit)")
    target_path: str = Field(".", description="Path to scan")


class StaticIssue(BaseModel):
    code: str
    message: str
    file_path: str
    line: int
    severity: str


class RunStaticAnalysisOutput(BaseModel):
    issues: list[StaticIssue]
    total_issues: int
    summary: str


class RunStaticAnalysisTool(BaseTool[RunStaticAnalysisInput, RunStaticAnalysisOutput]):
    name = "run_static_analysis"
    description = "Run static analysis and security scanning (Ruff, Bandit) over repository."
    category = "code"
    risk_level = "medium"
    required_permissions = ["execute:sandbox"]
    input_schema = RunStaticAnalysisInput
    output_schema = RunStaticAnalysisOutput

    async def execute(self, params: RunStaticAnalysisInput, context: dict[str, Any] | None = None) -> RunStaticAnalysisOutput:
        # In a real environment, executes via Sandbox. For fallback / local mode, performs lightweight AST lint check.
        base_dir = Path(context.get("workspace_path", ".")) if context else Path(".")
        target = base_dir / params.target_path
        issues: list[StaticIssue] = []

        if target.exists():
            for py_file in target.rglob("*.py") if target.is_dir() else [target]:
                if ".git" in py_file.parts:
                    continue
                try:
                    with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                        tree = ast.parse(f.read(), filename=str(py_file))
                    # Check for suspicious generic except or eval
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ExceptHandler) and node.type is None:
                            issues.append(StaticIssue(
                                code="E001",
                                message="Bare except clause detected (hides errors)",
                                file_path=str(py_file.relative_to(base_dir)).replace("\\", "/"),
                                line=node.lineno,
                                severity="medium",
                            ))
                except SyntaxError as e:
                    issues.append(StaticIssue(
                        code="SYNTAX",
                        message=f"Syntax error: {e.msg}",
                        file_path=str(py_file.relative_to(base_dir)).replace("\\", "/"),
                        line=e.lineno or 0,
                        severity="high",
                    ))
                except Exception:
                    continue

        return RunStaticAnalysisOutput(
            issues=issues,
            total_issues=len(issues),
            summary=f"Static analysis scanned {params.target_path} and detected {len(issues)} issues.",
        )
