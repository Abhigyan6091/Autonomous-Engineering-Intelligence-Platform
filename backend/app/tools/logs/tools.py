"""
Log search and analysis tools.

Reads plain-text application logs from the workspace and returns matching
entries with their parsed level and timestamp.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import BaseTool

# "2024-01-15 12:35:08 ERROR  POST /api/v1/checkout duration_ms=502 status=500"
_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?Z?)\s+"
    r"(?P<level>[A-Z]+)\s+(?P<message>.*)$"
)

# Log files are read from these locations relative to the workspace root.
_LOG_GLOBS = ("logs/*.log", "log/*.log", "*.log")

# Cap how much we read so a runaway log file cannot exhaust memory.
_MAX_LINES_SCANNED = 50_000


class LogEntry(BaseModel):
    timestamp: str | None = Field(None, description="Parsed timestamp, if the line carried one")
    level: str | None = Field(None, description="Parsed log level (INFO, WARNING, ERROR, ...)")
    message: str = Field(..., description="The log line content")
    source_file: str = Field(..., description="Log file the entry came from")
    line_number: int = Field(..., description="1-indexed line number within the source file")


class SearchLogsInput(BaseModel):
    query: str = Field(..., description="Substring to search for (case-insensitive), e.g. ERROR or Traceback")
    level: str | None = Field(None, description="Optional log level filter (INFO, WARNING, ERROR)")
    max_results: int = Field(100, ge=1, le=1000, description="Maximum number of entries to return")


class SearchLogsOutput(BaseModel):
    query: str
    entries: list[LogEntry]
    total_found: int = Field(..., description="Total matches found, which may exceed len(entries)")
    files_searched: list[str]
    summary: str


class SearchLogsTool(BaseTool[SearchLogsInput, SearchLogsOutput]):
    name = "search_logs"
    description = "Search application log files for errors, exceptions, and anomalous patterns."
    category = "log"
    risk_level = "low"
    required_permissions = ["read:logs"]
    input_schema = SearchLogsInput
    output_schema = SearchLogsOutput

    async def execute(
        self, params: SearchLogsInput, context: dict[str, Any] | None = None
    ) -> SearchLogsOutput:
        workspace = Path((context or {}).get("workspace_path", "."))

        log_files: list[Path] = []
        for pattern in _LOG_GLOBS:
            log_files.extend(sorted(workspace.glob(pattern)))
        # A file can match more than one glob (e.g. "*.log" and "logs/*.log").
        log_files = list(dict.fromkeys(log_files))

        needle = params.query.lower()
        wanted_level = params.level.upper() if params.level else None

        entries: list[LogEntry] = []
        total_found = 0
        lines_scanned = 0

        for path in log_files:
            if lines_scanned >= _MAX_LINES_SCANNED:
                break
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                # An unreadable log file should not fail the whole search.
                continue

            for index, line in enumerate(text.splitlines(), start=1):
                lines_scanned += 1
                if lines_scanned >= _MAX_LINES_SCANNED:
                    break

                line = line.rstrip()
                if not line or needle not in line.lower():
                    continue

                match = _LINE_RE.match(line)
                level = match.group("level") if match else None
                if wanted_level and level != wanted_level:
                    continue

                total_found += 1
                if len(entries) < params.max_results:
                    entries.append(
                        LogEntry(
                            timestamp=match.group("timestamp") if match else None,
                            level=level,
                            message=match.group("message") if match else line,
                            source_file=str(path),
                            line_number=index,
                        )
                    )

        file_names = [str(p) for p in log_files]
        if not log_files:
            summary = f"No log files found under '{workspace}'."
        else:
            summary = (
                f"Found {total_found} log entries matching '{params.query}' "
                f"across {len(log_files)} file(s)."
            )

        return SearchLogsOutput(
            query=params.query,
            entries=entries,
            total_found=total_found,
            files_searched=file_names,
            summary=summary,
        )
