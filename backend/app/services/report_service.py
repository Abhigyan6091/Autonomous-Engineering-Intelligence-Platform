"""
Report generation service — assembles the final investigation report from state.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.graph.state import AgentState
from app.llm.factory import get_primary_llm
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

REPORT_SYSTEM_PROMPT = """You are a technical writer generating a structured investigation report.

The report must be professional, precise, and actionable. Include:
1. Executive summary (2-3 sentences, non-technical)
2. Investigation timeline summary
3. Root cause analysis with evidence
4. Impact assessment
5. Recommendations and remediation steps
6. What was ruled out (rejected hypotheses)
7. Residual gaps and open questions

Be specific, reference evidence IDs, and avoid vague language.
"""

REPORT_USER_TEMPLATE = """
Investigation Mode: {mode}
Objective: {objective}
Duration: {duration}
Decision: {decision}

Root Cause: {root_cause}

Key Findings:
{findings}

Top Hypotheses (post-critique):
{hypotheses}

Evidence Gathered:
{evidence_summary}

Generate the final investigation report as structured JSON.
"""


class ReportSchema(BaseModel):
    executive_summary: str
    root_cause: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    impact_assessment: str
    timeline_summary: str
    recommendations: list[str]
    remediation_steps: list[str]
    ruled_out: list[str] = Field(default_factory=list, description="Rejected hypotheses")
    open_questions: list[str] = Field(default_factory=list)


async def generate_report(state: AgentState) -> dict[str, Any]:
    """Generate the final investigation report."""
    duration = "unknown"
    if state.budget.started_at:
        try:
            start = datetime.fromisoformat(state.budget.started_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(UTC) - start).total_seconds()
            duration = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
        except Exception:
            pass

    findings_text = "\n".join(
        f"- [{f.severity.upper()}] {f.claim} (confidence: {f.confidence:.2f})"
        for f in state.findings
    ) or "No explicit findings recorded."

    hypotheses_text = "\n".join(
        f"- [{h.confidence_tier}] {h.statement} (confidence: {h.confidence:.2f}, status: {h.status})"
        for h in sorted(state.hypotheses, key=lambda x: x.confidence, reverse=True)
    ) or "No hypotheses generated."

    evidence_summary = "\n".join(
        f"- [{e.source_type}] {e.source}: {e.summary or e.content[:100]}"
        for e in state.evidence[:15]
    ) or "No evidence gathered."

    root_cause_text = (
        state.root_cause.get("summary", "Not established") if state.root_cause else "Not established"
    )

    prompt = [
        {"role": "system", "content": REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": REPORT_USER_TEMPLATE.format(
            mode=state.mode,
            objective=state.objective,
            duration=duration,
            decision=state.decision or "inconclusive",
            root_cause=root_cause_text,
            findings=findings_text,
            hypotheses=hypotheses_text,
            evidence_summary=evidence_summary,
        )},
    ]

    try:
        llm = get_primary_llm().with_structured_output(ReportSchema)
        report: ReportSchema = await llm.ainvoke(prompt)

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": state.mode,
            "objective": state.objective,
            "decision": state.decision,
            "confidence": report.confidence,
            "executive_summary": report.executive_summary,
            "root_cause": report.root_cause,
            "impact_assessment": report.impact_assessment,
            "timeline_summary": report.timeline_summary,
            "recommendations": report.recommendations,
            "remediation_steps": report.remediation_steps,
            "ruled_out": report.ruled_out,
            "open_questions": report.open_questions,
            "evidence_count": len(state.evidence),
            "hypotheses_count": len(state.hypotheses),
            "findings": [
                {
                    "claim": f.claim,
                    "severity": f.severity,
                    "confidence": f.confidence,
                    "is_root_cause": f.is_root_cause,
                }
                for f in state.findings
            ],
            "token_usage": {
                "tokens_used": state.budget.tokens_used,
                "tokens_max": state.budget.tokens_max,
                "tool_calls_used": state.budget.tool_calls_used,
                "tool_calls_max": state.budget.tool_calls_max,
            },
        }
    except Exception as exc:
        logger.error("Report generation failed, building minimal report", error=str(exc))
        # Fallback: assemble a minimal report deterministically
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": state.mode,
            "objective": state.objective,
            "decision": state.decision or "inconclusive",
            "confidence": state.root_cause.get("confidence", 0.0) if state.root_cause else 0.0,
            "executive_summary": f"Investigation of: {state.objective[:200]}. Automated report generation encountered an error.",
            "root_cause": root_cause_text,
            "recommendations": ["Manual review of evidence required."],
            "findings": [{"claim": f.claim, "severity": f.severity, "confidence": f.confidence, "is_root_cause": f.is_root_cause} for f in state.findings],
            "error": str(exc),
        }
