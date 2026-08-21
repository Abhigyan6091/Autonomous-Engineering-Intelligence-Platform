"""
Tests for LangGraph state machine, reducer, and compilation.
"""
import pytest
from app.graph.state import AgentState, EvidenceItem, HypothesisItem, FindingItem
from app.graph.graph import build_investigation_graph, compile_graph, route_after_decision


def test_agent_state_initialization():
    state = AgentState(
        investigation_id="test-inv-001",
        project_id="test-proj-001",
        thread_id="test-thread-001",
        objective="Test investigation objective",
        mode="incident",
    )
    assert state.investigation_id == "test-inv-001"
    assert state.current_phase == "initialization"
    assert len(state.evidence) == 0
    assert len(state.hypotheses) == 0


def test_agent_state_helpers():
    state = AgentState(
        investigation_id="test-inv-001",
        project_id="test-proj-001",
        thread_id="test-thread-001",
        objective="Test objective",
        mode="incident",
    )

    # Add evidence
    ev = EvidenceItem(id="ev-1", source_type="git", source="diff", content="test diff")
    state = state.add_evidence(ev)
    assert len(state.evidence) == 1

    # Add hypothesis
    hyp = HypothesisItem(id="hyp-1", statement="Missing DB index", confidence=0.85, confidence_tier="highly_supported")
    state = state.add_hypothesis(hyp)
    assert len(state.hypotheses) == 1

    # Add finding
    f = FindingItem(id="f-1", claim="Root cause identified", confidence=0.9, confidence_tier="highly_supported", evidence_ids=["ev-1"], severity="critical", is_root_cause=True)
    state = state.add_finding(f)
    assert len(state.findings) == 1

    # Tool calls & budget
    state = state.increment_tool_call()
    assert state.budget.tool_calls_used == 1

    state = state.add_tokens(100, 50)
    assert state.budget.tokens_used == 150


def test_graph_compilation():
    graph = compile_graph(use_memory_checkpointer=True)
    assert graph is not None


def test_routing_logic():
    state = AgentState(
        investigation_id="test-inv-001",
        project_id="test-proj-001",
        thread_id="test-thread-001",
        objective="Test objective",
        mode="incident",
        decision="root_cause_established",
    )
    route = route_after_decision(state)
    assert route == "generate_report"

    state.decision = "insufficient_evidence"
    state.planner_iterations = 1
    state.max_planner_iterations = 3
    route = route_after_decision(state)
    assert route == "re_plan"
