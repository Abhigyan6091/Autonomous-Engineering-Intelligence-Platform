"""
Remediation Agent — generates a targeted, patch-based fix for the identified root cause.
"""
from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from app.graph.state import AgentState, RemediationProposal
from app.llm.factory import get_primary_llm
from app.core.security import redact_secrets

logger = structlog.get_logger(__name__)

REMEDIATION_SYSTEM_PROMPT = """You are a senior software engineer generating a targeted code patch.

Given the established root cause, supporting evidence, and the codebase context, produce:
1. A complete, minimal unified diff patch that fixes the root cause.
2. New or updated tests that verify the fix.
3. A clear rollback plan.
4. A risk assessment for the change.

Rules:
- Patches must be minimal and targeted — do not refactor unrelated code.
- All test additions must use pytest and be fully runnable.
- The patch MUST address the specific root cause; do not address unrelated issues.
- Output strictly structured JSON.
- Do NOT introduce new dependencies without justification.
"""

REMEDIATION_USER_TEMPLATE = """
Root Cause: {root_cause}

Evidence Summary:
{evidence}

Relevant Code Context:
{code_context}

Generate a minimal, targeted patch to fix this root cause.
"""


class TestAddition(BaseModel):
    file_path: str
    test_code: str
    description: str


class RemediationSchema(BaseModel):
    root_cause_summary: str
    patch_content: str = Field(description="Unified diff patch content")
    test_additions: list[TestAddition] = Field(default_factory=list)
    rollback_plan: str
    risk_assessment: str
    expected_outcome: str
    confidence: float = Field(ge=0.0, le=1.0)


class RemediationAgent:
    """Generates targeted code patches for identified root causes."""

    def __init__(self) -> None:
        self.llm = get_primary_llm().with_structured_output(RemediationSchema)

    async def generate_proposal(self, state: AgentState) -> RemediationProposal:
        root_cause_summary = (
            state.root_cause.get("summary", "Unknown root cause")
            if state.root_cause else "Unknown root cause"
        )

        # Build evidence context (sanitized)
        evidence_parts = []
        for e in state.evidence[:10]:
            content = redact_secrets(e.content[:500])
            evidence_parts.append(f"[{e.source_type}] {e.source}: {content}")
        evidence_text = "\n".join(evidence_parts) or "No evidence available."

        # Extract code context from evidence
        code_evidence = [e for e in state.evidence if e.source_type in ("git", "code")]
        code_context = "\n".join(
            redact_secrets(e.content[:800]) for e in code_evidence[:3]
        ) or "No code context available."

        prompt = [
            {"role": "system", "content": REMEDIATION_SYSTEM_PROMPT},
            {"role": "user", "content": REMEDIATION_USER_TEMPLATE.format(
                root_cause=root_cause_summary,
                evidence=evidence_text,
                code_context=code_context,
            )},
        ]

        try:
            result: RemediationSchema = await self.llm.ainvoke(prompt)
            logger.info("Remediation proposal generated", confidence=result.confidence)
            return RemediationProposal(
                root_cause_summary=result.root_cause_summary,
                patch_content=result.patch_content,
                test_additions=[{"file_path": t.file_path, "test_code": t.test_code, "description": t.description} for t in result.test_additions],
                rollback_plan=result.rollback_plan,
                risk_assessment=result.risk_assessment,
                expected_outcome=result.expected_outcome,
                confidence=result.confidence,
            )
        except Exception as exc:
            logger.error("Remediation agent failed", error=str(exc))
            return RemediationProposal(
                root_cause_summary=root_cause_summary,
                patch_content="# Patch generation failed — manual remediation required.",
                rollback_plan="Revert the most recent deployment via CI/CD rollback.",
                risk_assessment="Unknown — manual assessment required.",
                expected_outcome="Manual investigation required.",
                confidence=0.0,
            )
