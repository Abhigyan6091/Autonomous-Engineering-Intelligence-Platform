"""
Structured logging configuration using structlog.
All log entries include investigation context (trace ID, investigation ID, etc.)
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """Configure structlog for structured JSON or pretty-text logging."""
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    # Configure stdlib logging to capture third-party library logs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Silence noisy loggers
    for noisy_logger in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Shared processors applied to every log entry
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_FORMAT == "json":
        # Production: JSON output
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: pretty console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_investigation_context(
    investigation_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
    tool_execution_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    """
    Bind investigation-specific context to the current log context.
    All subsequent log statements in this request will include these fields.
    """
    ctx: dict[str, str] = {}
    if investigation_id:
        ctx["investigation_id"] = investigation_id
    if task_id:
        ctx["task_id"] = task_id
    if agent_id:
        ctx["agent_id"] = agent_id
    if tool_execution_id:
        ctx["tool_execution_id"] = tool_execution_id
    if trace_id:
        ctx["trace_id"] = trace_id
    structlog.contextvars.bind_contextvars(**ctx)


def clear_context() -> None:
    """Clear the structlog context (call at end of request)."""
    structlog.contextvars.clear_contextvars()


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound logger for the given module name."""
    return structlog.get_logger(name)
