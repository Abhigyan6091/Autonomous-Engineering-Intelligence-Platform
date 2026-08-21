"""
Decision Agent — determines if root cause is established and what action to take next.
"""
from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from app.graph.state import AgentState, FindingItem
from app.llm.factory import get_primary_llm
import uuid

logger = structlog.get_logger(__name__)

DECISION_SYSTEM_PROMPT = """You are the final decision-maker in a software incident investigation.

Given the hypotheses (with confidence scores and critique), evidence, and investigation gaps, decide:
1. Whether the root cause has been established with sufficient confidence.
2. What the primary finding and root cause are.
3. Whether another investigation iteration is needed.

Decision options:
- "root_cause_established": High-confidence hypothesis (>0.6) with strong evidence support.
- "insufficient_evidence": Best hypothesis is below 0.5 confidence; more investigation needed.
- "investigation_failed": Critical tool failures or contradictory evidence preventing conclusions.
- "inconclusive": Evidence gathered but no clear pattern emerged; report partial findings.
"""

DECISION_USER_TEMPLATE = """
Objective: {objective}
Mode: {mode}
Planner iterations used: {iterations}/{max_iterations}

=== HYPOTHESES ===
{hypotheses_text}

=== FINDINGS SO FAR ===
{findings_text}

=== INVESTIGATION GAPS ===
{gaps_text}

Make your decision and extract the primary root cause finding if established.
"""


class DecisionSchema(BaseModel):
    decision: str = Field(description="root_cause_established | insufficient_evidence | investigation_failed | inconclusive")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall investigation confidence")
    root_cause_summary: str = Field(description="Summary of the root cause (or 'Not established')")
    primary_hypothesis_id: str | None = Field(None, description="ID of the leading hypothesis")
    investigation_gaps: list[str] = Field(default_factory=list, description="What is still unknown")
    supervisor_notes: list[str] = Field(default_factory=list, description="Notes for the next iteration")
    findings: list[FindingSchema] = Field(default_factory=list)


class FindingSchema(BaseModel):
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: str = Field(description="critical | high | medium | low | info")
    category: str | None = None
    is_root_cause: bool = False
    evidence_ids: list[str] = Field(default_factory=list)


_VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}

# Models reach for severity words outside the allowed set; map the common
# ones rather than failing the whole investigation on a wording choice.
_SEVERITY_ALIASES = {
    "sev0": "critical", "sev_0": "critical", "sev1": "critical", "sev_1": "critical",
    "blocker": "critical", "fatal": "critical", "urgent": "critical", "p0": "critical",
    "severe": "high", "major": "high", "sev2": "high", "sev_2": "high", "p1": "high",
    "moderate": "medium", "normal": "medium", "warning": "medium",
    "sev3": "medium", "sev_3": "medium", "p2": "medium",
    "minor": "low", "trivial": "low", "sev4": "low", "sev_4": "low", "p3": "low",
    "informational": "info", "note": "info", "notice": "info",
}

_VALID_DECISIONS = {
    "root_cause_established",
    "insufficient_evidence",
    "investigation_failed",
    "budget_exceeded",
    "inconclusive",
}

_DECISION_ALIASES = {
    "root_cause_found": "root_cause_established",
    "root_cause_identified": "root_cause_established",
    "established": "root_cause_established",
    "resolved": "root_cause_established",
    "confirmed": "root_cause_established",
    "insufficient": "insufficient_evidence",
    "not_enough_evidence": "insufficient_evidence",
    "needs_more_evidence": "insufficient_evidence",
    "failed": "investigation_failed",
    "error": "investigation_failed",
    "unknown": "inconclusive",
    "undetermined": "inconclusive",
    "unclear": "inconclusive",
}


def _normalize(raw: str | None, valid: set[str], aliases: dict[str, str], fallback: str) -> str:
    """Coerce an LLM-supplied enum string into one of the allowed literals."""
    value = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value in valid:
        return value
    if value in aliases:
        return aliases[value]
    logger.warning("Unrecognized value from decision agent", value=raw, fallback=fallback)
    return fallback


class DecisionAgent:
    """Synthesizes investigation results into a definitive root cause decision."""

    def __init__(self) -> None:
        self.llm = get_primary_llm().with_structured_output(DecisionSchema)

    async def decide(self, state: AgentState) -> dict:
        hypotheses_text = "\n".join(
            f"[{h.id[:8]}] ({h.confidence_tier}) {h.statement} | Confidence: {h.confidence:.2f} | Status: {h.status}"
            for h in sorted(state.hypotheses, key=lambda x: x.confidence, reverse=True)
        )
        findings_text = "\n".join(f"- {f.claim}" for f in state.findings) or "None yet."
        gaps_text = "\n".join(f"- {g}" for g in state.investigation_gaps) or "None identified."

        prompt = [
            {"role": "system", "content": DECISION_SYSTEM_PROMPT},
            {"role": "user", "content": DECISION_USER_TEMPLATE.format(
                objective=state.objective,
                mode=state.mode,
                iterations=state.planner_iterations,
                max_iterations=state.max_planner_iterations,
                hypotheses_text=hypotheses_text,
                findings_text=findings_text,
                gaps_text=gaps_text,
            )},
        ]

        try:
            result: DecisionSchema = await self.llm.ainvoke(prompt)
            logger.info("Decision made", decision=result.decision, confidence=result.confidence)

            # Build finding objects
            new_findings = []
            for f in result.findings:
                tier = "highly_supported" if f.confidence >= 0.8 else "strong" if f.confidence >= 0.6 else "plausible" if f.confidence >= 0.4 else "weak"
                new_findings.append(FindingItem(
                    id=str(uuid.uuid4()),
                    claim=f.claim,
                    confidence=f.confidence,
                    confidence_tier=tier,
                    evidence_ids=f.evidence_ids,
                    severity=_normalize(f.severity, _VALID_SEVERITIES, _SEVERITY_ALIASES, "medium"),
                    category=f.category,
                    is_root_cause=f.is_root_cause,
                ))

            decision = _normalize(
                result.decision, _VALID_DECISIONS, _DECISION_ALIASES, "inconclusive"
            )

            root_cause = None
            if decision == "root_cause_established" and result.root_cause_summary != "Not established":
                root_cause = {
                    "summary": result.root_cause_summary,
                    "confidence": result.confidence,
                    "primary_hypothesis_id": result.primary_hypothesis_id,
                }

            return {
                "decision": decision,
                "findings": [*state.findings, *new_findings],
                "root_cause": root_cause,
                "investigation_gaps": result.investigation_gaps,
                "supervisor_notes": [*state.supervisor_notes, *result.supervisor_notes],
                "current_phase": "decision",
            }
        except Exception as exc:
            logger.error("Decision agent failed", error=str(exc))
            return {
                "decision": "inconclusive",
                "current_phase": "decision",
                "last_error": str(exc),
            }
