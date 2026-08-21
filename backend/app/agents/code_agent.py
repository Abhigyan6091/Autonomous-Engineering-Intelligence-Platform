"""
Code Analysis Agent — inspects source code, git diffs, and static analysis results.
"""
from __future__ import annotations

import uuid
import structlog

from app.graph.state import AgentState, EvidenceItem
from app.tools.code.tools import SearchCodeTool, RunStaticAnalysisTool
from app.tools.git.tools import GetGitDiffTool, ListCommitsTool
from app.tools.filesystem.tools import ListFilesTool, ReadFileTool
from app.llm.factory import get_primary_llm
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

CODE_AGENT_SYSTEM_PROMPT = """You are a code analysis agent in a software investigation platform.

Your job: systematically analyze the codebase using the provided tools to gather evidence relevant to the investigation objective.

Strategy:
1. List and understand the repository structure.
2. Inspect recent git commits and diffs for changes related to the objective.
3. Search for relevant code patterns, function definitions, error handlers.
4. Run static analysis to detect code quality issues.
5. Read specific files that appear most relevant to the issue.

Return the most significant findings as structured evidence.
"""


class EvidenceSummarySchema(BaseModel):
    source: str
    source_type: str = "code"
    content: str
    summary: str
    quality_score: float = Field(ge=0.0, le=1.0, default=0.7)


class EvidenceListSchema(BaseModel):
    items: list[EvidenceSummarySchema]


class CodeAgent:
    """Specialized agent for code and git analysis."""

    async def run(self, state: AgentState) -> list[EvidenceItem]:
        active_task = next((t for t in state.planned_tasks if t.task_id == state.active_task_id), None)
        objective = active_task.objective if active_task else state.objective
        context = {"workspace_path": state.metadata.get("workspace_path", ".")}

        # Deterministically gather code evidence
        evidence_items: list[EvidenceItem] = []

        # 1. Get recent git diff
        diff_tool = GetGitDiffTool()
        diff_result = await diff_tool.execute(diff_tool.input_schema(), context=context)
        if diff_result.diff and not diff_result.diff.startswith("Git diff error"):
            evidence_items.append(EvidenceItem(
                id=str(uuid.uuid4()),
                source_type="git",
                source="HEAD~1..HEAD",
                content=diff_result.diff[:3000],
                summary=f"Git diff: {len(diff_result.files_changed)} files changed (+{diff_result.insertions}/-{diff_result.deletions})",
                quality_score=0.9,
            ))

        # 2. List commits
        commits_tool = ListCommitsTool()
        commits_result = await commits_tool.execute(commits_tool.input_schema(max_count=5), context=context)
        if commits_result.commits:
            content = "\n".join(f"{c.hexsha} {c.author}: {c.message[:100]}" for c in commits_result.commits)
            evidence_items.append(EvidenceItem(
                id=str(uuid.uuid4()),
                source_type="git",
                source="recent_commits",
                content=content,
                summary=f"Last {len(commits_result.commits)} git commits reviewed.",
                quality_score=0.8,
            ))

        # 3. Static analysis
        static_tool = RunStaticAnalysisTool()
        static_result = await static_tool.execute(static_tool.input_schema(), context=context)
        if static_result.issues:
            content = "\n".join(f"{i.file_path}:{i.line} [{i.code}] {i.message}" for i in static_result.issues[:20])
            evidence_items.append(EvidenceItem(
                id=str(uuid.uuid4()),
                source_type="code",
                source="static_analysis",
                content=content,
                summary=f"Static analysis detected {static_result.total_issues} issues.",
                quality_score=0.75,
            ))

        # 4. LLM-guided specific search based on objective
        try:
            llm = get_primary_llm().with_structured_output(EvidenceListSchema)
            search_tool = SearchCodeTool()
            # Extract keywords from objective
            keywords_prompt = [
                {"role": "user", "content": f"Extract 1-3 code search terms (function names, class names, variable names, error strings) from this investigation objective: {objective}\n\nRespond with just a comma-separated list of terms."}
            ]
            from langchain_openai import ChatOpenAI
            keyword_llm = get_primary_llm()
            kw_response = await keyword_llm.ainvoke(keywords_prompt)
            keywords = [k.strip() for k in kw_response.content.split(",")][:3]

            for kw in keywords:
                search_result = await search_tool.execute(search_tool.input_schema(query=kw), context=context)
                if search_result.matches:
                    content = "\n".join(f"{m.file_path}:{m.line_number}: {m.line_content}" for m in search_result.matches[:10])
                    evidence_items.append(EvidenceItem(
                        id=str(uuid.uuid4()),
                        source_type="code",
                        source=f"search:{kw}",
                        content=content,
                        summary=f"Code search for '{kw}' found {search_result.total_matches} matches.",
                        quality_score=0.7,
                    ))
        except Exception as exc:
            logger.warning("LLM-guided code search failed", error=str(exc))

        return evidence_items


async def _run_agent(state: AgentState, agent: CodeAgent, agent_name: str) -> dict:
    """Generic agent runner with error handling."""
    try:
        items = await agent.run(state)
        return {"evidence": [*state.evidence, *items]}
    except Exception as exc:
        logger.error("Agent execution failed", agent=agent_name, error=str(exc))
        return {"last_error": str(exc), "failed_node": agent_name}
