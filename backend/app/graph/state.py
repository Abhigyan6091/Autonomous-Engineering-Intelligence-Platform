"""
LangGraph AgentState — the central data structure for all investigation workflows.

This is the single source of truth for an in-progress investigation.
It is persisted to PostgreSQL at every checkpoint via the LangGraph checkpointer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


# =============================================================================
# Sub-models used within AgentState
# =============================================================================

class EvidenceItem(BaseModel):
    """A single piece of evidence gathered during the investigation."""
    id: str
    source_type: str   # git | logs | metrics | code | docs | test
    source: str        # File path, URL, query, etc.
    content: str
    summary: str | None = None
    quality_score: float = 0.5
    tool_execution_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    provenance: dict[str, Any] = Field(default_factory=dict)


def merge_evidence(
    left: list["EvidenceItem"], right: list["EvidenceItem"]
) -> list["EvidenceItem"]:
    """
    Reducer for evidence gathered by concurrently fanned-out agent nodes.

    Agent nodes run in parallel and each returns only its own items, so
    updates must accumulate rather than overwrite. Items are keyed by id so a
    replayed or checkpoint-resumed node cannot duplicate its evidence.
    """
    merged: dict[str, EvidenceItem] = {item.id: item for item in left}
    for item in right:
        merged[item.id] = item
    return list(merged.values())


class HypothesisItem(BaseModel):
    """A hypothesis about the root cause."""
    id: str
    statement: str
    confidence: float = 0.0
    confidence_tier: Literal["weak", "plausible", "strong", "highly_supported"] = "weak"
    status: Literal["open", "supported", "rejected", "inconclusive"] = "open"
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    testable_predictions: list[str] = Field(default_factory=list)
    critique_notes: str | None = None


class FindingItem(BaseModel):
    """A confirmed finding from the investigation."""
    id: str
    claim: str
    confidence: float
    confidence_tier: str
    evidence_ids: list[str]
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: str | None = None
    is_root_cause: bool = False


class PlannedTask(BaseModel):
    """A task created by the Planner agent."""
    task_id: str
    assigned_agent: str
    description: str
    objective: str
    dependencies: list[str] = Field(default_factory=list)
    priority: int = 5
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    result: dict[str, Any] | None = None
    tools_likely_needed: list[str] = Field(default_factory=list)


class RemediationProposal(BaseModel):
    """A proposed fix from the Remediation agent."""
    root_cause_summary: str
    patch_content: str
    test_additions: list[dict[str, str]] = Field(default_factory=list)
    rollback_plan: str
    risk_assessment: str
    expected_outcome: str
    confidence: float
    approval_id: str | None = None


class BudgetState(BaseModel):
    """Tracks resource usage against budgets."""
    tokens_used: int = 0
    tokens_max: int = 500_000
    tool_calls_used: int = 0
    tool_calls_max: int = 200
    started_at: str | None = None
    max_duration_seconds: int = 3600

    @property
    def is_token_budget_exceeded(self) -> bool:
        return self.tokens_used >= self.tokens_max

    @property
    def is_tool_budget_exceeded(self) -> bool:
        return self.tool_calls_used >= self.tool_calls_max


# =============================================================================
# AgentState — the main LangGraph state type
# =============================================================================

class AgentState(BaseModel):
    """
    The complete state of an investigation workflow.

    LangGraph will checkpoint this state to PostgreSQL at every node transition.
    The `messages` field uses the add_messages reducer for chat history.
    All other fields use last-writer-wins semantics.
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    investigation_id: str
    project_id: str
    thread_id: str

    # ── Objective ─────────────────────────────────────────────────────────────
    objective: str
    mode: Literal["incident", "audit", "remediation"]
    priority: str = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ── LangGraph messages ────────────────────────────────────────────────────
    # Uses the add_messages reducer — new messages are appended, not replaced
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # ── Workflow phase ────────────────────────────────────────────────────────
    current_phase: Literal[
        "initialization",
        "planning",
        "execution",
        "evidence_merge",
        "hypothesis_generation",
        "hypothesis_testing",
        "critic",
        "decision",
        "reporting",
        "remediation",
        "awaiting_approval",
        "remediation_execution",
        "verification",
        "complete",
        "failed",
    ] = "initialization"

    # ── Task management ────────────────────────────────────────────────────────
    planned_tasks: list[PlannedTask] = Field(default_factory=list)
    active_task_id: str | None = None

    # ── Evidence ───────────────────────────────────────────────────────────────
    evidence: Annotated[list[EvidenceItem], merge_evidence] = Field(default_factory=list)

    # ── Hypotheses ─────────────────────────────────────────────────────────────
    hypotheses: list[HypothesisItem] = Field(default_factory=list)

    # ── Findings ───────────────────────────────────────────────────────────────
    findings: list[FindingItem] = Field(default_factory=list)

    # ── Root cause ─────────────────────────────────────────────────────────────
    root_cause: dict[str, Any] | None = None

    # ── Remediation ────────────────────────────────────────────────────────────
    remediation_proposal: RemediationProposal | None = None
    approval_status: Literal["pending", "approved", "rejected"] | None = None

    # ── Final report ───────────────────────────────────────────────────────────
    final_report: dict[str, Any] | None = None

    # ── Error handling and retries ─────────────────────────────────────────────
    retry_count: int = 0
    last_error: str | None = None
    failed_node: str | None = None
    recovery_attempts: int = 0
    max_retries: int = 3

    # ── Budget tracking ────────────────────────────────────────────────────────
    budget: BudgetState = Field(default_factory=BudgetState)

    # ── Iteration tracking ─────────────────────────────────────────────────────
    planner_iterations: int = 0
    max_planner_iterations: int = 3

    # ── Context for agents ─────────────────────────────────────────────────────
    supervisor_notes: list[str] = Field(default_factory=list)
    investigation_gaps: list[str] = Field(default_factory=list)
    decision: Literal[
        "root_cause_established",
        "insufficient_evidence",
        "investigation_failed",
        "budget_exceeded",
        "inconclusive",
    ] | None = None
    next_action: Literal[
        "generate_report",
        "continue_investigation",
        "escalate",
        "partial_report",
    ] | None = None

    model_config = {"arbitrary_types_allowed": True}

    def add_evidence(self, item: EvidenceItem) -> "AgentState":
        """Return a new state with the evidence item added."""
        return self.model_copy(update={"evidence": [*self.evidence, item]})

    def add_hypothesis(self, hypothesis: HypothesisItem) -> "AgentState":
        """Return a new state with the hypothesis added or updated."""
        existing_ids = {h.id for h in self.hypotheses}
        if hypothesis.id in existing_ids:
            updated = [h if h.id != hypothesis.id else hypothesis for h in self.hypotheses]
        else:
            updated = [*self.hypotheses, hypothesis]
        return self.model_copy(update={"hypotheses": updated})

    def add_finding(self, finding: FindingItem) -> "AgentState":
        """Return a new state with the finding added."""
        return self.model_copy(update={"findings": [*self.findings, finding]})

    def increment_tool_call(self) -> "AgentState":
        """Increment the tool call counter."""
        new_budget = self.budget.model_copy(
            update={"tool_calls_used": self.budget.tool_calls_used + 1}
        )
        return self.model_copy(update={"budget": new_budget})

    def add_tokens(self, input_tokens: int, output_tokens: int) -> "AgentState":
        """Track LLM token usage."""
        new_budget = self.budget.model_copy(
            update={"tokens_used": self.budget.tokens_used + input_tokens + output_tokens}
        )
        return self.model_copy(update={"budget": new_budget})
