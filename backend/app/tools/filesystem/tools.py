"""
Filesystem exploration tools with path sanitization and boundary checks.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool


class ListFilesInput(BaseModel):
    directory_path: str = Field(".", description="Relative directory path to list")
    recursive: bool = Field(False, description="Whether to list recursively")
    max_depth: int = Field(3, description="Maximum directory recursion depth")


class FileItem(BaseModel):
    path: str
    is_dir: bool
    size_bytes: int


class ListFilesOutput(BaseModel):
    files: list[FileItem]
    total_count: int


class ListFilesTool(BaseTool[ListFilesInput, ListFilesOutput]):
    name = "list_files"
    description = "List files and directories within a target repository workspace."
    category = "filesystem"
    risk_level = "low"
    required_permissions = ["read:repo"]
    input_schema = ListFilesInput
    output_schema = ListFilesOutput

    async def execute(self, params: ListFilesInput, context: dict[str, Any] | None = None) -> ListFilesOutput:
        base_dir = (Path(context.get("workspace_path", ".")) if context else Path(".")).resolve()
        target = (base_dir / params.directory_path).resolve()

        # Enforce boundary check (no path traversal outside workspace)
        if not str(target).startswith(str(base_dir)):
            target = base_dir

        items: list[FileItem] = []
        if not target.exists():
            return ListFilesOutput(files=[], total_count=0)

        if params.recursive:
            for root, dirs, files in os.walk(target):
                rel_root = Path(root).resolve().relative_to(base_dir)
                depth = len(rel_root.parts)
                if depth > params.max_depth:
                    continue
                for d in dirs:
                    p = (Path(root) / d).resolve()
                    items.append(FileItem(path=str(p.relative_to(base_dir)).replace("\\", "/"), is_dir=True, size_bytes=0))
                for f in files:
                    p = (Path(root) / f).resolve()
                    size = p.stat().st_size if p.exists() else 0
                    items.append(FileItem(path=str(p.relative_to(base_dir)).replace("\\", "/"), is_dir=False, size_bytes=size))
        else:
            for entry in target.iterdir():
                resolved_entry = entry.resolve()
                items.append(FileItem(
                    path=str(resolved_entry.relative_to(base_dir)).replace("\\", "/"),
                    is_dir=resolved_entry.is_dir(),
                    size_bytes=resolved_entry.stat().st_size if resolved_entry.is_file() else 0
                ))

        return ListFilesOutput(files=items[:500], total_count=len(items))


class ReadFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path of file to read")
    start_line: int = Field(1, description="1-indexed start line number")
    max_lines: int = Field(300, description="Maximum lines to read")


class ReadFileOutput(BaseModel):
    file_path: str
    content: str
    total_lines: int
    truncated: bool


class ReadFileTool(BaseTool[ReadFileInput, ReadFileOutput]):
    name = "read_file"
    description = "Read source code or file contents within the workspace with line range limits."
    category = "filesystem"
    risk_level = "low"
    required_permissions = ["read:repo"]
    input_schema = ReadFileInput
    output_schema = ReadFileOutput

    async def execute(self, params: ReadFileInput, context: dict[str, Any] | None = None) -> ReadFileOutput:
        base_dir = Path(context.get("workspace_path", ".")) if context else Path(".")
        target = (base_dir / params.file_path).resolve()

        if not str(target).startswith(str(base_dir.resolve())):
            return ReadFileOutput(file_path=params.file_path, content="Error: Path outside workspace", total_lines=0, truncated=False)

        if not target.is_file():
            return ReadFileOutput(file_path=params.file_path, content=f"Error: File '{params.file_path}' not found", total_lines=0, truncated=False)

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            total_lines = len(lines)
            start_idx = max(0, params.start_line - 1)
            end_idx = min(total_lines, start_idx + params.max_lines)
            selected = lines[start_idx:end_idx]
            return ReadFileOutput(
                file_path=params.file_path,
                content="".join(selected),
                total_lines=total_lines,
                truncated=end_idx < total_lines,
            )
        except Exception as exc:
            return ReadFileOutput(file_path=params.file_path, content=f"Error reading file: {exc}", total_lines=0, truncated=False)
