"""
LLM token accounting.

A LangChain callback records token usage for every model call, and a context
variable attributes those calls to the investigation currently running. This
keeps the agents free of bookkeeping: anything they invoke is counted.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any

import structlog
from langchain_core.callbacks import AsyncCallbackHandler

logger = structlog.get_logger(__name__)

# Set for the duration of an investigation run; None outside one.
current_investigation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_investigation_id", default=None
)


@contextmanager
def investigation_context(investigation_id: str):
    """Attribute all LLM calls made inside this block to one investigation."""
    token = current_investigation_id.set(investigation_id)
    try:
        yield
    finally:
        current_investigation_id.reset(token)


def _extract_usage(response: Any) -> tuple[int, int]:
    """Pull (input_tokens, output_tokens) out of an LLM response."""
    for generations in getattr(response, "generations", []) or []:
        for generation in generations:
            message = getattr(generation, "message", None)
            usage = getattr(message, "usage_metadata", None) if message else None
            if usage:
                return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))

    # Some providers report usage only on the aggregate response.
    output = getattr(response, "llm_output", None) or {}
    usage = output.get("token_usage") or output.get("usage") or {}
    if usage:
        return (
            int(usage.get("prompt_tokens", usage.get("input_tokens", 0))),
            int(usage.get("completion_tokens", usage.get("output_tokens", 0))),
        )

    return 0, 0


class TokenUsageCallback(AsyncCallbackHandler):
    """Records token usage per LLM call against the active investigation."""

    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        investigation_id = current_investigation_id.get()
        if not investigation_id:
            return

        input_tokens, output_tokens = _extract_usage(response)
        if not input_tokens and not output_tokens:
            return

        model = "unknown"
        output = getattr(response, "llm_output", None) or {}
        if isinstance(output, dict):
            model = output.get("model") or output.get("model_name") or model

        try:
            await record_llm_usage(investigation_id, model, input_tokens, output_tokens)
        except Exception as exc:
            # Accounting must never break an investigation.
            logger.warning("Could not record LLM usage", error=str(exc))


async def record_llm_usage(
    investigation_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Write one usage row and roll the totals onto the investigation."""
    from sqlalchemy import select

    from app.core.config import settings
    from app.db.database import AsyncSessionLocal
    from app.db.models import Investigation, LLMUsage

    async with AsyncSessionLocal() as db:
        db.add(
            LLMUsage(
                investigation_id=investigation_id,
                model=model,
                provider=settings.LLM_PROVIDER,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )

        result = await db.execute(
            select(Investigation).where(Investigation.id == investigation_id)
        )
        investigation = result.scalar_one_or_none()
        if investigation:
            investigation.budget_tokens_used = (
                investigation.budget_tokens_used or 0
            ) + input_tokens + output_tokens

        await db.commit()


async def record_tool_call(investigation_id: str | None, count: int = 1) -> None:
    """Increment the tool-call counter shown against the budget."""
    if not investigation_id or count <= 0:
        return

    from sqlalchemy import select

    from app.db.database import AsyncSessionLocal
    from app.db.models import Investigation

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Investigation).where(Investigation.id == investigation_id)
            )
            investigation = result.scalar_one_or_none()
            if investigation:
                investigation.budget_tool_calls_used = (
                    investigation.budget_tool_calls_used or 0
                ) + count
                await db.commit()
    except Exception as exc:
        logger.warning("Could not record tool call", error=str(exc))
