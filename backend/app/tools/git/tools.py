"""
Git Inspection and safe branch/patch tools.
Uses controlled Git service layer — never arbitrary shell execution.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import git
from pydantic import BaseModel, Field
from app.tools.base import BaseTool


class GetGitDiffInput(BaseModel):
    commit_a: str = Field("HEAD~1", description="Base commit / branch / tag")
    commit_b: str = Field("HEAD", description="Target commit / branch / tag")
    file_path: str | None = Field(None, description="Optional path to filter diff")


class GetGitDiffOutput(BaseModel):
    diff: str
    files_changed: list[str]
    insertions: int
    deletions: int


class GetGitDiffTool(BaseTool[GetGitDiffInput, GetGitDiffOutput]):
    name = "get_git_diff"
    description = "Inspect git diff between two commits or branches."
    category = "git"
    risk_level = "low"
    required_permissions = ["read:git"]
    input_schema = GetGitDiffInput
    output_schema = GetGitDiffOutput

    async def execute(self, params: GetGitDiffInput, context: dict[str, Any] | None = None) -> GetGitDiffOutput:
        workspace_path = context.get("workspace_path", ".") if context else "."
        try:
            repo = git.Repo(workspace_path)
            diff_text = repo.git.diff(params.commit_a, params.commit_b, "--", params.file_path or ".")
            # Calculate stats
            diff_index = repo.commit(params.commit_a).diff(repo.commit(params.commit_b))
            files = [d.b_path or d.a_path for d in diff_index if (d.b_path or d.a_path)]
            return GetGitDiffOutput(
                diff=diff_text[:15000],  # Limit size to prevent memory explosion
                files_changed=files,
                insertions=len([l for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++")]),
                deletions=len([l for l in diff_text.splitlines() if l.startswith("-") and not l.startswith("---")]),
            )
        except Exception as exc:
            return GetGitDiffOutput(diff=f"Git diff error: {exc}", files_changed=[], insertions=0, deletions=0)


class ListCommitsInput(BaseModel):
    max_count: int = Field(10, description="Max commits to return")
    branch: str = Field("HEAD", description="Branch name or HEAD")
    file_path: str | None = Field(None, description="Optional path to filter commit history")


class CommitSummary(BaseModel):
    hexsha: str
    author: str
    message: str
    committed_datetime: str


class ListCommitsOutput(BaseModel):
    commits: list[CommitSummary]


class ListCommitsTool(BaseTool[ListCommitsInput, ListCommitsOutput]):
    name = "list_commits"
    description = "List recent git commits for a branch or file."
    category = "git"
    risk_level = "low"
    required_permissions = ["read:git"]
    input_schema = ListCommitsInput
    output_schema = ListCommitsOutput

    async def execute(self, params: ListCommitsInput, context: dict[str, Any] | None = None) -> ListCommitsOutput:
        workspace_path = context.get("workspace_path", ".") if context else "."
        try:
            repo = git.Repo(workspace_path)
            commits = list(repo.iter_commits(params.branch, max_count=params.max_count, paths=params.file_path))
            return ListCommitsOutput(
                commits=[
                    CommitSummary(
                        hexsha=c.hexsha[:8],
                        author=f"{c.author.name} <{c.author.email}>",
                        message=c.message.strip(),
                        committed_datetime=c.committed_datetime.isoformat(),
                    )
                    for c in commits
                ]
            )
        except Exception:
            return ListCommitsOutput(commits=[])
