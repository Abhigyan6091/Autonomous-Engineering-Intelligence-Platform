"""
Critic Agent — stress-tests hypotheses and flags logical fallacies.
"""
from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from app.graph.state import AgentState, HypothesisItem
from app.llm.factory import get_primary_llm

logger = structlog.get_logger(__name__)

CRITIC_SYSTEM_PROMPT = """You are a rigorous scientific critic reviewing software incident hypotheses.

Your job is to:
1. Challenge each hypothesis with counter-arguments and alternative explanations.
2. Detect correlation-vs-causation fallacies.
3. Identify hypotheses that lack sufficient evidence.
4. Suggest what missing evidence would be decisive.
5. Downgrade confidence where warranted; reject clearly unsupported hypotheses.

Be systematic, fair, and precise. Adjust confidence scores up OR down based on logical strength.
"""

CRITIC_USER_TEMPLATE = """
Investigation Objective: {objective}

=== HYPOTHESES TO REVIEW ===
{hypotheses_text}
=== END ===

=== FULL EVIDENCE SUMMARY ===
{evidence_summary}
=== END ===

For each hypothesis, provide a critique and an adjusted confidence score.
"""


class HypothesisCritique(BaseModel):
    hypothesis_id: str
    critique: str = Field(description="Specific critique of this hypothesis")
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    status: str = Field(description="open | supported | rejected | inconclusive")
    missing_evidence: list[str] = Field(default_factory=list, description="What evidence would confirm/deny this?")


class CritiqueListSchema(BaseModel):
    critiques: list[HypothesisCritique]


def _confidence_tier(c: float) -> str:
    if c >= 0.8:
        return "highly_supported"
    elif c >= 0.6:
        return "strong"
    elif c >= 0.4:
        return "plausible"
    return "weak"


class CriticAgent:
    """Reviews hypotheses for logical soundness and evidence quality."""

    def __init__(self) -> None:
        self.llm = get_primary_llm().with_structured_output(CritiqueListSchema)

    async def critique(self, state: AgentState) -> list[HypothesisItem]:
        hypotheses_text = "\n".join(
            f"ID: {h.id[:8]}\nStatement: {h.statement}\nConfidence: {h.confidence:.2f}\n"
            f"Supporting: {h.supporting_evidence_ids}\n"
            for h in state.hypotheses
        )
        evidence_summary = "\n".join(
            f"[{e.id[:8]}] ({e.source_type}) {e.summary or e.content[:200]}"
            for e in state.evidence[:15]
        )

        prompt = [
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": CRITIC_USER_TEMPLATE.format(
                objective=state.objective,
                hypotheses_text=hypotheses_text,
                evidence_summary=evidence_summary,
            )},
        ]

        try:
            result: CritiqueListSchema = await self.llm.ainvoke(prompt)
            critique_map = {c.hypothesis_id[:8]: c for c in result.critiques}

            updated = []
            for h in state.hypotheses:
                critique = critique_map.get(h.id[:8])
                if critique:
                    h = h.model_copy(update={
                        "confidence": critique.adjusted_confidence,
                        "confidence_tier": _confidence_tier(critique.adjusted_confidence),
                        "status": critique.status,
                        "critique_notes": critique.critique,
                    })
                updated.append(h)

            logger.info("Critic completed", hypotheses_reviewed=len(updated))
            return updated
        except Exception as exc:
            logger.error("Critic failed", error=str(exc))
            return state.hypotheses
