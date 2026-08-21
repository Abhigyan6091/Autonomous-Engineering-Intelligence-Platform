"""
LangGraph StateGraph definition — the primary orchestration engine.

This graph implements the full investigation workflow with:
- Dynamic task planning and fan-out (Send)
- Parallel agent execution
- Evidence merging
- Hypothesis generation and testing
- Critic review
- Decision routing
- Human approval interrupt
- Remediation execution
- Verification

The graph is checkpointed to PostgreSQL, making investigations durable
across process restarts.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import AgentState, BudgetState, PlannedTask

logger = structlog.get_logger(__name__)

# Specialist agent nodes available for dynamic fan-out. Must match the
# node names registered on the graph in build_graph().
VALID_AGENT_NODES = [
    "code_agent",
    "log_agent",
    "test_agent",
    "metrics_agent",
    "research_agent",
]


# =============================================================================
# Graph Nodes
# =============================================================================

async def initialize_investigation_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Initialize the investigation.
    Sets up the initial state and records the start in the database.
    """
    logger.info(
        "Investigation initializing",
        investigation_id=state.investigation_id,
        mode=state.mode,
        objective=state.objective[:100],
    )

    # Update investigation status in database
    await _update_investigation_db(
        state.investigation_id,
        {"status": "planning", "started_at": datetime.now(UTC)},
    )

    # Emit initialization event
    await _emit_event(state.investigation_id, "investigation.started", {
        "mode": state.mode,
        "objective": state.objective,
    })

    return {
        "current_phase": "planning",
        "budget": BudgetState(
            started_at=datetime.now(UTC).isoformat(),
        ),
    }


async def planner_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Planner agent creates the investigation task graph.
    Uses LLM reasoning to decompose the objective into concrete tasks.
    """
    from app.agents.planner import PlannerAgent

    logger.info(
        "Planner running",
        investigation_id=state.investigation_id,
        iteration=state.planner_iterations,
    )

    await _emit_event(state.investigation_id, "agent.started", {"agent": "planner"})

    try:
        planner = PlannerAgent()
        tasks = await planner.create_plan(state)

        await _emit_event(state.investigation_id, "agent.thinking_completed", {
            "agent": "planner",
            "tasks_created": len(tasks),
        })

        # Persist tasks to database
        await _save_tasks_to_db(state.investigation_id, tasks)

        return {
            "planned_tasks": tasks,
            "current_phase": "execution",
            "planner_iterations": state.planner_iterations + 1,
        }
    except Exception as exc:
        logger.error("Planner failed", error=str(exc), exc_info=True)
        return {
            "last_error": str(exc),
            "failed_node": "planner",
            "current_phase": "failed",
        }


def route_tasks(state: AgentState) -> list[Any]:
    """
    Conditional-edge router: fan-out tasks to specialized agents via Send.

    This must be a routing function (not a node): LangGraph only accepts a
    list of Send objects from a conditional edge. Returning them from a node
    raises InvalidUpdateError("Expected dict, got [Send(...)]").
    """
    from langgraph.types import Send

    if isinstance(state, dict):
        state = AgentState.model_validate(state)

    pending_tasks = [t for t in state.planned_tasks if t.status == "pending"]

    if not pending_tasks:
        logger.warning("No pending tasks to route", investigation_id=state.investigation_id)
        # With no work to fan out, skip straight to merging what we have.
        return ["evidence_merge"]

    # Create parallel sends for all pending tasks
    sends = []
    for task in pending_tasks:
        # Node names are registered without a "_node" suffix.
        agent_node = task.assigned_agent
        if agent_node not in VALID_AGENT_NODES:
            logger.warning(
                "Unknown agent for task, skipping",
                task_id=task.task_id,
                agent=task.assigned_agent,
            )
            continue
        sends.append(Send(agent_node, {**state.model_dump(), "active_task_id": task.task_id}))
        logger.info(
            "Task routed",
            task_id=task.task_id,
            agent=agent_node,
        )

    if not sends:
        logger.warning(
            "No task matched a known agent",
            investigation_id=state.investigation_id,
        )
        return ["evidence_merge"]

    return sends


async def _run_agent(
    state: AgentState, agent: Any, agent_name: str
) -> dict[str, Any]:
    """
    Execute one specialist agent and fold its evidence back into the graph state.

    Agent nodes run concurrently via Send fan-out, so this returns only the
    keys this agent owns. `evidence` uses a merging reducer, so the returned
    list is the agent's new evidence, not the full set.
    """
    # Nodes reached through Send receive the raw payload dict rather than the
    # graph's state model, so coerce before touching attributes.
    if isinstance(state, dict):
        state = AgentState.model_validate(state)

    task_id = state.active_task_id
    await _emit_event(state.investigation_id, "agent.started", {
        "agent": agent_name,
        "task_id": task_id,
    })
    await _update_task_db(task_id, {"status": "running", "started_at": datetime.now(UTC)})

    try:
        items = await agent.run(state)
    except Exception as exc:
        logger.error(
            "Agent failed",
            investigation_id=state.investigation_id,
            agent=agent_name,
            task_id=task_id,
            error=str(exc),
            exc_info=True,
        )
        await _update_task_db(
            task_id,
            {"status": "failed", "error": str(exc), "completed_at": datetime.now(UTC)},
        )
        await _emit_event(state.investigation_id, "agent.failed", {
            "agent": agent_name,
            "task_id": task_id,
            "error": str(exc),
        })
        # One agent failing must not abort the investigation; the remaining
        # agents' evidence still flows to evidence_merge.
        return {"evidence": []}

    items = list(items or [])
    for item in items:
        item.provenance = {**(item.provenance or {}), "agent": agent_name, "task_id": task_id}

    await _save_evidence_to_db(state.investigation_id, items)
    await _update_task_db(
        task_id, {"status": "completed", "completed_at": datetime.now(UTC)}
    )
    await _emit_event(state.investigation_id, "agent.completed", {
        "agent": agent_name,
        "task_id": task_id,
        "evidence_count": len(items),
    })

    logger.info(
        "Agent completed",
        investigation_id=state.investigation_id,
        agent=agent_name,
        task_id=task_id,
        evidence_count=len(items),
    )

    # Only `evidence` is returned here. Agent nodes run concurrently, and keys
    # without a reducer (planned_tasks, budget) reject concurrent writes with
    # InvalidUpdateError; task status is tracked on the Task rows instead.
    return {"evidence": items}


async def code_agent_node(state: AgentState) -> dict[str, Any]:
    """Node: Code analysis agent."""
    from app.agents.code_agent import CodeAgent
    return await _run_agent(state, CodeAgent(), "code_agent")


async def log_agent_node(state: AgentState) -> dict[str, Any]:
    """Node: Log analysis agent."""
    from app.agents.log_agent import LogAgent
    return await _run_agent(state, LogAgent(), "log_agent")


async def test_agent_node(state: AgentState) -> dict[str, Any]:
    """Node: Test analysis agent."""
    from app.agents.test_agent import TestAgent
    return await _run_agent(state, TestAgent(), "test_agent")


async def metrics_agent_node(state: AgentState) -> dict[str, Any]:
    """Node: Metrics analysis agent."""
    from app.agents.data_agent import DataAgent
    return await _run_agent(state, DataAgent(), "metrics_agent")


async def research_agent_node(state: AgentState) -> dict[str, Any]:
    """Node: Research/documentation agent."""
    from app.agents.research_agent import ResearchAgent
    return await _run_agent(state, ResearchAgent(), "research_agent")


async def evidence_merge_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Merge all evidence gathered by parallel agents.
    Deduplicates, ranks by quality, and prepares for hypothesis generation.
    """
    logger.info(
        "Evidence merge",
        investigation_id=state.investigation_id,
        evidence_count=len(state.evidence),
    )

    # Deduplicate evidence by content hash
    seen_hashes: set[int] = set()
    unique_evidence = []
    for item in state.evidence:
        h = hash(item.content[:200])
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique_evidence.append(item)

    await _emit_event(state.investigation_id, "evidence.merged", {
        "total": len(state.evidence),
        "unique": len(unique_evidence),
    })

    # Agent nodes cannot write planned_tasks (concurrent writes to a key with
    # no reducer), so the dispatched tasks are marked done here, after fan-in.
    completed_tasks = [
        t.model_copy(update={"status": "completed"}) if t.status == "pending" else t
        for t in state.planned_tasks
    ]

    # The `evidence` reducer already merges by id, so re-emitting the list
    # here would be a no-op; only the phase and task statuses advance.
    return {
        "planned_tasks": completed_tasks,
        "current_phase": "hypothesis_generation",
    }


async def hypothesis_generation_node(state: AgentState) -> dict[str, Any]:
    """Node: Hypothesis agent generates hypotheses from evidence."""
    from app.agents.hypothesis_agent import HypothesisAgent

    agent = HypothesisAgent()
    hypotheses = await agent.generate_hypotheses(state)

    await _emit_event(state.investigation_id, "hypothesis.created", {
        "count": len(hypotheses),
    })

    # Save to database
    await _save_hypotheses_to_db(state.investigation_id, hypotheses)

    return {
        "hypotheses": hypotheses,
        "current_phase": "critic",
    }


async def critic_node(state: AgentState) -> dict[str, Any]:
    """Node: Critic agent challenges hypotheses."""
    from app.agents.critic_agent import CriticAgent

    agent = CriticAgent()
    updated_hypotheses = await agent.critique(state)

    await _emit_event(state.investigation_id, "critic.completed", {
        "hypotheses_reviewed": len(state.hypotheses),
        "rejected": sum(1 for h in updated_hypotheses if h.status == "rejected"),
    })

    return {
        "hypotheses": updated_hypotheses,
        "current_phase": "decision",
    }


async def decision_node(state: AgentState) -> dict[str, Any]:
    """Node: Decision agent determines if root cause is established."""
    from app.agents.decision_agent import DecisionAgent

    agent = DecisionAgent()
    result = await agent.decide(state)

    await _emit_event(state.investigation_id, "decision.made", {
        "decision": result["decision"],
        "confidence": result.get("confidence", 0),
    })

    return result


async def report_generation_node(state: AgentState) -> dict[str, Any]:
    """Node: Generate the final investigation report."""
    from app.services.report_service import generate_report

    report = await generate_report(state)

    # Save to database
    await _update_investigation_db(state.investigation_id, {
        "status": "completed",
        "completed_at": datetime.now(UTC),
        "confidence": report.get("confidence", 0),
        "final_report": report,
    })

    await _emit_event(state.investigation_id, "investigation.completed", {
        "confidence": report.get("confidence", 0),
        "findings_count": len(state.findings),
    })

    return {
        "final_report": report,
        "current_phase": "complete",
    }


async def remediation_proposal_node(state: AgentState) -> dict[str, Any]:
    """Node: Remediation agent generates a proposed fix."""
    from app.agents.remediation_agent import RemediationAgent

    agent = RemediationAgent()
    proposal = await agent.generate_proposal(state)

    # Create approval record
    approval_id = await _create_approval(
        state.investigation_id,
        action="apply_patch",
        risk_level="high",
        description="Apply generated code patch to fix the identified root cause",
        payload={"patch": proposal.patch_content},
    )

    await _emit_event(state.investigation_id, "approval.requested", {
        "approval_id": approval_id,
        "action": "apply_patch",
        "risk_level": "high",
    })

    return {
        "remediation_proposal": proposal.model_copy(update={"approval_id": approval_id}),
        "current_phase": "awaiting_approval",
    }


async def human_approval_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Wait for human approval before executing remediation.

    This node uses LangGraph's interrupt mechanism — the graph is paused
    and will not proceed until the approval API endpoint is called.
    """
    from langgraph.types import interrupt

    approval_id = state.remediation_proposal.approval_id if state.remediation_proposal else None

    logger.info(
        "Awaiting human approval",
        investigation_id=state.investigation_id,
        approval_id=approval_id,
    )

    # This interrupt pauses the graph execution
    # The graph will resume when the approval API sends the approval decision
    approval_result = interrupt({
        "type": "human_approval_required",
        "approval_id": approval_id,
        "message": "Human approval required before applying the code patch",
        "investigation_id": state.investigation_id,
    })

    return {
        "approval_status": approval_result.get("decision", "rejected"),
    }


async def remediation_executor_node(state: AgentState) -> dict[str, Any]:
    """Node: Execute the approved remediation in an isolated branch."""
    logger.info(
        "Executing remediation",
        investigation_id=state.investigation_id,
        approval_status=state.approval_status,
    )

    if state.approval_status != "approved":
        logger.info("Remediation rejected by human")
        return {"current_phase": "complete"}

    # TODO Phase 7: Implement actual patch application
    await _emit_event(state.investigation_id, "remediation.executing", {
        "status": "started",
    })

    return {"current_phase": "verification"}


async def verification_node(state: AgentState) -> dict[str, Any]:
    """Node: Verify the applied remediation by running tests."""
    logger.info("Running verification", investigation_id=state.investigation_id)
    # TODO Phase 7: Implement test-based verification
    return {"current_phase": "complete"}


async def error_recovery_node(state: AgentState) -> dict[str, Any]:
    """Node: Attempt to recover from a failed node."""
    logger.warning(
        "Error recovery",
        investigation_id=state.investigation_id,
        failed_node=state.failed_node,
        error=state.last_error,
        recovery_attempts=state.recovery_attempts,
    )

    if state.recovery_attempts >= state.max_retries:
        await _update_investigation_db(state.investigation_id, {"status": "failed"})
        return {"current_phase": "failed"}

    return {
        "recovery_attempts": state.recovery_attempts + 1,
        "current_phase": "planning",  # Re-plan from scratch
        "last_error": None,
        "failed_node": None,
    }


# =============================================================================
# Conditional Edges (Routers)
# =============================================================================

def route_after_decision(state: AgentState) -> str:
    """Router: determine next step after the decision node."""
    # Budget exceeded
    if state.budget.is_token_budget_exceeded or state.budget.is_tool_budget_exceeded:
        return "partial_report"

    decision = state.decision

    if decision == "root_cause_established":
        return "generate_report"
    elif decision == "insufficient_evidence":
        if state.planner_iterations < state.max_planner_iterations:
            return "re_plan"
        return "partial_report"
    elif decision == "investigation_failed":
        return "error_recovery"
    else:
        return "partial_report"


def route_after_report(state: AgentState) -> str:
    """Router: determine next step after report generation."""
    if state.mode == "remediation" or state.metadata.get("request_remediation", False):
        return "remediation"
    return "end"


def route_after_approval(state: AgentState) -> str:
    """Router: determine next step after human approval decision."""
    if state.approval_status == "approved":
        return "execute"
    return "end"


def route_after_phase(state: AgentState) -> str:
    """Router: general phase-based routing."""
    if state.current_phase == "failed":
        return "error_recovery"
    if state.budget.is_token_budget_exceeded or state.budget.is_tool_budget_exceeded:
        return "budget_exceeded"
    return "continue"


# =============================================================================
# Graph Builder
# =============================================================================

def build_investigation_graph() -> StateGraph:
    """
    Build and return the LangGraph StateGraph for investigations.

    Graph structure:
        START → initialize → planner → route_tasks → [agents in parallel]
            → evidence_merge → hypothesis_generation → critic → decision
            → [report | re-plan | recovery]
            → [remediation → human_approval → executor → verification]
            → END
    """
    graph = StateGraph(AgentState)

    # ── Add all nodes ──────────────────────────────────────────────────────
    graph.add_node("initialize", initialize_investigation_node)
    graph.add_node("planner", planner_node)

    # Specialized agent nodes
    graph.add_node("code_agent", code_agent_node)
    graph.add_node("log_agent", log_agent_node)
    graph.add_node("test_agent", test_agent_node)
    graph.add_node("metrics_agent", metrics_agent_node)
    graph.add_node("research_agent", research_agent_node)

    # Core workflow nodes
    graph.add_node("evidence_merge", evidence_merge_node)
    graph.add_node("hypothesis_generation", hypothesis_generation_node)
    graph.add_node("critic", critic_node)
    graph.add_node("decision", decision_node)
    graph.add_node("report_generation", report_generation_node)

    # Remediation nodes
    graph.add_node("remediation_proposal", remediation_proposal_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("remediation_executor", remediation_executor_node)
    graph.add_node("verification", verification_node)

    # Error handling
    graph.add_node("error_recovery", error_recovery_node)

    # ── Linear edges ───────────────────────────────────────────────────────
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "planner")
    # planner → parallel agents (via Send, dynamic fan-out)
    graph.add_conditional_edges(
        "planner",
        route_tasks,
        VALID_AGENT_NODES + ["evidence_merge"],
    )

    # All parallel agents → evidence_merge
    for agent_node in ["code_agent", "log_agent", "test_agent", "metrics_agent", "research_agent"]:
        graph.add_edge(agent_node, "evidence_merge")

    graph.add_edge("evidence_merge", "hypothesis_generation")
    graph.add_edge("hypothesis_generation", "critic")
    graph.add_edge("critic", "decision")

    # ── Conditional edge from decision ─────────────────────────────────────
    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {
            "generate_report": "report_generation",
            "re_plan": "planner",
            "error_recovery": "error_recovery",
            "partial_report": "report_generation",
        },
    )

    # ── Conditional edge from report ───────────────────────────────────────
    graph.add_conditional_edges(
        "report_generation",
        route_after_report,
        {
            "remediation": "remediation_proposal",
            "end": END,
        },
    )

    # ── Remediation flow ───────────────────────────────────────────────────
    graph.add_edge("remediation_proposal", "human_approval")

    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "execute": "remediation_executor",
            "end": END,
        },
    )

    graph.add_edge("remediation_executor", "verification")
    graph.add_edge("verification", END)

    # ── Error recovery ─────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "error_recovery",
        lambda s: "retry" if s.recovery_attempts < s.max_retries else "give_up",
        {
            "retry": "planner",
            "give_up": END,
        },
    )

    return graph


def compile_graph(use_memory_checkpointer: bool = True):
    """
    Compile the graph with a checkpointer.

    In development: uses MemorySaver (in-memory, not durable)
    In production: uses PostgreSQL-backed checkpointer
    """
    graph = build_investigation_graph()

    if use_memory_checkpointer:
        checkpointer = MemorySaver()
    else:
        # PostgreSQL checkpointer (Phase 6)
        # from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        # checkpointer = await AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
        checkpointer = MemorySaver()  # Fallback until Phase 6

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_approval"],  # Interrupt before human approval node
    )


# =============================================================================
# Main entry point — called by the investigations API
# =============================================================================

async def run_investigation(investigation_id: str) -> None:
    """
    Launch an investigation workflow.
    Called as a background task from the investigations API.
    """
    from app.db.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.db.models import Investigation

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Investigation).where(Investigation.id == investigation_id)
        )
        investigation = result.scalar_one_or_none()
        if not investigation:
            logger.error("Investigation not found", investigation_id=investigation_id)
            return

    # Build initial state
    initial_state = AgentState(
        investigation_id=investigation_id,
        project_id=investigation.project_id,
        thread_id=investigation.langgraph_thread_id or str(uuid.uuid4()),
        objective=investigation.objective,
        mode=investigation.mode,
        priority=investigation.priority,
        metadata=investigation.metadata_,
    )

    config = {
        "configurable": {
            "thread_id": initial_state.thread_id,
        },
        "recursion_limit": 50,
    }

    app_graph = compile_graph()

    logger.info(
        "Starting investigation graph",
        investigation_id=investigation_id,
        thread_id=initial_state.thread_id,
    )

    try:
        # Run the graph
        async for event in app_graph.astream(initial_state.model_dump(), config=config):
            # Events are already persisted via audit events in each node
            logger.debug("Graph event", event_keys=list(event.keys()))
    except Exception as exc:
        logger.error(
            "Graph execution failed",
            investigation_id=investigation_id,
            error=str(exc),
            exc_info=True,
        )
        await _update_investigation_db(investigation_id, {
            "status": "failed",
            "last_error": str(exc),
        })
        raise


# =============================================================================
# Database helpers (used by graph nodes)
# =============================================================================

async def _update_investigation_db(investigation_id: str, updates: dict[str, Any]) -> None:
    """Update investigation fields in the database."""
    from app.db.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.db.models import Investigation

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Investigation).where(Investigation.id == investigation_id)
            )
            inv = result.scalar_one_or_none()
            if inv:
                for key, value in updates.items():
                    if key == "metadata":
                        inv.metadata_ = value
                    else:
                        setattr(inv, key, value)
                await db.commit()
    except Exception as exc:
        logger.error("Failed to update investigation DB", error=str(exc))


async def _emit_event(
    investigation_id: str, event_type: str, payload: dict[str, Any]
) -> None:
    """Create an audit event for SSE streaming."""
    from app.db.database import AsyncSessionLocal
    from app.db.models import AuditEvent

    try:
        async with AsyncSessionLocal() as db:
            event = AuditEvent(
                investigation_id=investigation_id,
                event_type=event_type,
                actor="system",
                payload=payload,
            )
            db.add(event)
            await db.commit()
    except Exception as exc:
        logger.error("Failed to emit event", error=str(exc))


async def _update_task_db(task_id: str | None, updates: dict[str, Any]) -> None:
    """Update a task row; no-op when the task was never persisted."""
    if not task_id:
        return
    from sqlalchemy import select

    from app.db.database import AsyncSessionLocal
    from app.db.models import Task

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                return
            for key, value in updates.items():
                setattr(task, key, value)
            await db.commit()
    except Exception as exc:
        logger.error("Failed to update task", task_id=task_id, error=str(exc))


async def _save_evidence_to_db(investigation_id: str, items: list) -> None:
    """Persist evidence items gathered by an agent."""
    if not items:
        return
    from app.db.database import AsyncSessionLocal
    from app.db.models import Evidence

    try:
        async with AsyncSessionLocal() as db:
            for item in items:
                db.add(Evidence(
                    id=item.id,
                    investigation_id=investigation_id,
                    source_type=item.source_type,
                    source=item.source,
                    content=item.content,
                    summary=item.summary,
                    quality_score=item.quality_score,
                    tool_execution_id=item.tool_execution_id,
                    provenance=item.provenance or {},
                ))
            await db.commit()
    except Exception as exc:
        logger.error("Failed to save evidence to DB", error=str(exc))


async def _save_tasks_to_db(investigation_id: str, tasks: list[PlannedTask]) -> None:
    """Save planned tasks to the database."""
    from app.db.database import AsyncSessionLocal
    from app.db.models import Task

    try:
        async with AsyncSessionLocal() as db:
            for task in tasks:
                db_task = Task(
                    id=task.task_id,
                    investigation_id=investigation_id,
                    assigned_agent=task.assigned_agent,
                    description=task.description,
                    objective=task.objective,
                    status="pending",
                    dependencies=task.dependencies,
                )
                db.add(db_task)
            await db.commit()
    except Exception as exc:
        logger.error("Failed to save tasks to DB", error=str(exc))


async def _save_hypotheses_to_db(investigation_id: str, hypotheses: list) -> None:
    """Save hypotheses to the database."""
    from app.db.database import AsyncSessionLocal
    from app.db.models import Hypothesis

    try:
        async with AsyncSessionLocal() as db:
            for h in hypotheses:
                db_h = Hypothesis(
                    id=h.id,
                    investigation_id=investigation_id,
                    statement=h.statement,
                    confidence=h.confidence,
                    confidence_tier=h.confidence_tier,
                    status=h.status,
                    supporting_evidence_ids=h.supporting_evidence_ids,
                    contradicting_evidence_ids=h.contradicting_evidence_ids,
                )
                db.add(db_h)
            await db.commit()
    except Exception as exc:
        logger.error("Failed to save hypotheses to DB", error=str(exc))


async def _create_approval(
    investigation_id: str,
    action: str,
    risk_level: str,
    description: str,
    payload: dict[str, Any],
) -> str:
    """Create a human approval record and return its ID."""
    from app.db.database import AsyncSessionLocal
    from app.db.models import Approval

    approval_id = str(uuid.uuid4())
    try:
        async with AsyncSessionLocal() as db:
            approval = Approval(
                id=approval_id,
                investigation_id=investigation_id,
                action=action,
                risk_level=risk_level,
                description=description,
                payload=payload,
            )
            db.add(approval)
            await db.commit()
    except Exception as exc:
        logger.error("Failed to create approval", error=str(exc))
    return approval_id
