"""
Evaluation Framework Runner for AEIP.
Evaluates the autonomous platform against the benchmark dataset of 10 engineering incidents.

Run: python scripts/run_evaluation.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

BENCHMARK_INCIDENTS = [
    {
        "id": "INC-001",
        "name": "Database Latency Regression (Missing Index)",
        "objective": "The checkout API is experiencing p95 latency of 284ms, exceeding SLA of 200ms after recent deployment. Investigate and remediate.",
        "ground_truth_root_cause": "Migration 3a8f2b1 removed the index on inventory_items.product_id, resulting in sequential table scans during cart checkout loops.",
        "expected_tools": ["get_git_diff", "search_logs", "read_schema", "query_latency"],
        "critical_evidence_keywords": ["product_id", "ix_inventory_items", "Seq Scan", "3a8f2b1"],
    },
    {
        "id": "INC-002",
        "name": "Memory Leak in Event Dispatcher",
        "objective": "Worker processes in payment-worker service are restarting due to Out-Of-Memory (OOM) kills every 4 hours.",
        "ground_truth_root_cause": "Unbounded global dictionary `_listeners` accumulating callback references without weakrefs.",
        "expected_tools": ["search_code", "search_logs", "run_static_analysis"],
        "critical_evidence_keywords": ["_listeners", "OOMKilled", "memory_leak"],
    },
    {
        "id": "INC-003",
        "name": "Connection Pool Exhaustion",
        "objective": "Database connections exhausted during morning peak traffic. App reporting OperationalError: connection pool limit reached.",
        "ground_truth_root_cause": "DB_POOL_SIZE environment variable configured to 5 instead of production baseline 50 in Helm values.",
        "expected_tools": ["read_file", "search_logs", "query_error_rate"],
        "critical_evidence_keywords": ["DB_POOL_SIZE", "pool_size", "connection pool limit"],
    },
    {
        "id": "INC-004",
        "name": "Dependency Incompatibility",
        "objective": "Pydantic v2 upgrade broke JSON serialization in legacy webhook receiver.",
        "ground_truth_root_cause": "`model.dict()` removed in Pydantic v2, replaced by `model.model_dump()`.",
        "expected_tools": ["get_git_diff", "search_logs", "run_tests"],
        "critical_evidence_keywords": [".dict()", "model_dump", "Pydantic"],
    },
    {
        "id": "INC-005",
        "name": "API Contract Type Mismatch",
        "objective": "Downstream billing service returns HTTP 422 Unprocessable Entity on valid order submissions.",
        "ground_truth_root_cause": "Order service sending order_id as integer, but billing service schema updated to require UUID string.",
        "expected_tools": ["search_code", "search_documentation", "search_logs"],
        "critical_evidence_keywords": ["422", "order_id", "UUID", "type mismatch"],
    },
    {
        "id": "INC-006",
        "name": "Redundant Middleware Latency",
        "objective": "API gateway throughput dropped by 40% after refactoring middleware stack.",
        "ground_truth_root_cause": "Duplicate authentication middleware registered in both app.py and router level.",
        "expected_tools": ["get_git_diff", "search_code", "query_latency"],
        "critical_evidence_keywords": ["middleware", "add_middleware", "duplicate"],
    },
    {
        "id": "INC-007",
        "name": "Downstream Timeout Worker Starvation",
        "objective": "Thread pool exhaustion in shipping service when external carrier API is degraded.",
        "ground_truth_root_cause": "Missing HTTP socket timeout on carrier API requests, blocking worker threads indefinitely.",
        "expected_tools": ["search_code", "query_latency", "search_logs"],
        "critical_evidence_keywords": ["timeout", "requests.get", "socket timeout"],
    },
    {
        "id": "INC-008",
        "name": "Unhandled Optional Attribute Exception",
        "objective": "Guest users encountering HTTP 500 on checkout completion.",
        "ground_truth_root_cause": "AttributeError accessing `user.profile.billing_address` when user is anonymous guest.",
        "expected_tools": ["search_logs", "search_code", "run_tests"],
        "critical_evidence_keywords": ["AttributeError", "guest", "NoneType"],
    },
    {
        "id": "INC-009",
        "name": "Inventory Race Condition (Overselling)",
        "objective": "Flash sale resulted in 12 orders for only 10 available inventory units.",
        "ground_truth_root_cause": "Deduction without `SELECT ... FOR UPDATE` row lock allowed concurrent transactions to read stale quantity.",
        "expected_tools": ["search_code", "read_schema", "get_git_diff"],
        "critical_evidence_keywords": ["SELECT FOR UPDATE", "race condition", "with_for_update"],
    },
    {
        "id": "INC-010",
        "name": "Missing Production Secret",
        "objective": "Stripe webhook callbacks failing with signature verification error in production cluster.",
        "ground_truth_root_cause": "STRIPE_WEBHOOK_SECRET missing from Kubernetes Secret manifest.",
        "expected_tools": ["search_logs", "read_file", "search_documentation"],
        "critical_evidence_keywords": ["STRIPE_WEBHOOK_SECRET", "SignatureVerificationError", "secret"],
    },
]


# Incidents whose scenario actually exists in the seeded demo repository.
# The other benchmark entries have no corresponding code to investigate, so
# running them would score the harness, not the platform.
SUPPORTED_INCIDENTS = {"INC-001"}

# Absolute: this module chdir()s into backend/, so a relative path would
# resolve to backend/demo_repo and silently evaluate an empty workspace.
WORKSPACE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "demo_repo", "checkout-api")
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower())


def score_root_cause(text: str, incident: dict) -> tuple[float, list[str]]:
    """
    Fraction of the incident's critical evidence keywords present in `text`.

    Deterministic and inspectable — no LLM judge, so the score cannot drift
    between runs.
    """
    haystack = _norm(text)
    keywords = incident["critical_evidence_keywords"]
    hits = [k for k in keywords if _norm(k).strip() and _norm(k).strip() in haystack]
    return (len(hits) / len(keywords) if keywords else 0.0), hits


async def evaluate_incident(incident: dict) -> dict:
    """Run one benchmark incident end to end and score the result."""
    from sqlalchemy import select

    from app.db.database import AsyncSessionLocal
    from app.db.models import Evidence, Finding, Hypothesis, Investigation
    from app.graph.graph import run_investigation

    async with AsyncSessionLocal() as db:
        inv = Investigation(
            project_id="demo-project-001",
            objective=incident["objective"],
            mode="incident",
            status="created",
            priority="critical",
            created_by="evaluation",
            metadata_={"workspace_path": WORKSPACE, "service_name": "checkout-api"},
            langgraph_thread_id=str(uuid.uuid4()),
        )
        db.add(inv)
        await db.commit()
        await db.refresh(inv)
        inv_id = inv.id

    started = time.perf_counter()
    error = None
    try:
        await run_investigation(inv_id)
    except Exception as exc:  # noqa: BLE001 - recorded as a failed run
        error = str(exc)
    elapsed = time.perf_counter() - started

    async with AsyncSessionLocal() as db:
        inv = (await db.execute(
            select(Investigation).where(Investigation.id == inv_id)
        )).scalar_one()
        findings = list((await db.execute(
            select(Finding).where(Finding.investigation_id == inv_id)
        )).scalars().all())
        hypotheses = list((await db.execute(
            select(Hypothesis).where(Hypothesis.investigation_id == inv_id)
        )).scalars().all())
        evidence = list((await db.execute(
            select(Evidence).where(Evidence.investigation_id == inv_id)
        )).scalars().all())

    # Root cause accuracy: score the reported root cause and any findings.
    root_cause_text = " ".join(filter(None, [
        json.dumps(inv.final_report or {}),
        " ".join(f.claim for f in findings),
    ]))
    rca, hits = score_root_cause(root_cause_text, incident)

    # Evidence grounding: does the collected evidence contain the real signals?
    evidence_text = " ".join(f"{e.summary or ''} {e.content or ''}" for e in evidence)
    ev_recall, ev_hits = score_root_cause(evidence_text, incident)

    grounded = [f for f in findings if f.evidence_ids]
    resolved = [h for h in hypotheses if h.status != "open"]

    return {
        "incident_id": incident["id"],
        "name": incident["name"],
        "investigation_id": inv_id,
        "status": inv.status,
        "error": error,
        "rca_accuracy": round(rca, 3),
        "rca_keywords_hit": hits,
        "evidence_recall": round(ev_recall, 3),
        "evidence_keywords_hit": ev_hits,
        "evidence_count": len(evidence),
        "findings_count": len(findings),
        "grounded_findings": len(grounded),
        "evidence_grounded_rate": round(len(grounded) / len(findings), 3) if findings else None,
        "hypotheses_count": len(hypotheses),
        "hypotheses_resolved": len(resolved),
        "hypothesis_resolution_rate": round(len(resolved) / len(hypotheses), 3) if hypotheses else None,
        "tokens_used": inv.budget_tokens_used,
        "tool_calls_used": inv.budget_tool_calls_used,
        "expected_min_tool_calls": len(incident["expected_tools"]),
        "tool_efficiency": (
            round(len(incident["expected_tools"]) / inv.budget_tool_calls_used, 3)
            if inv.budget_tool_calls_used else None
        ),
        "confidence": inv.confidence,
        "elapsed_seconds": round(elapsed, 1),
        "status_ok": inv.status == "completed",
    }


def summarise(results: list[dict]) -> dict:
    n = len(results)
    done = [r for r in results if r["status_ok"]]
    lat = [r["elapsed_seconds"] for r in results]
    grounded = [r["evidence_grounded_rate"] for r in results if r["evidence_grounded_rate"] is not None]
    hyp = [r["hypothesis_resolution_rate"] for r in results if r["hypothesis_resolution_rate"] is not None]
    eff = [r["tool_efficiency"] for r in results if r["tool_efficiency"] is not None]
    return {
        "benchmark_count": n,
        "root_cause_accuracy": round(sum(r["rca_accuracy"] for r in results) / n, 3) if n else None,
        "evidence_recall": round(sum(r["evidence_recall"] for r in results) / n, 3) if n else None,
        "evidence_grounded_diagnosis_rate": round(sum(grounded) / len(grounded), 3) if grounded else None,
        "hypothesis_verification_rate": round(sum(hyp) / len(hyp), 3) if hyp else None,
        "investigation_success_rate": round(len(done) / n, 3) if n else None,
        "tool_call_efficiency": round(sum(eff) / len(eff), 3) if eff else None,
        "mean_tool_calls": round(sum(r["tool_calls_used"] for r in results) / n, 1) if n else None,
        "mean_tokens": round(sum(r["tokens_used"] for r in results) / n, 1) if n else None,
        "latency_seconds": {
            "min": round(min(lat), 1), "mean": round(sum(lat) / len(lat), 1), "max": round(max(lat), 1)
        } if lat else None,
    }


async def remediation_stats() -> dict[str, Any]:
    """
    Lifetime remediation outcomes, read from the audit trail.

    Remediation needs a human decision, so it cannot run inside the automated
    benchmark; these counts come from every remediation the platform has
    actually attempted.
    """
    from sqlalchemy import func, select

    from app.db.database import AsyncSessionLocal
    from app.db.models import AuditEvent

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AuditEvent.event_type, func.count())
            .where(AuditEvent.event_type.in_([
                "remediation.executing",
                "remediation.applied",
                "remediation.failed",
                "remediation.rolled_back",
                "verification.completed",
            ]))
            .group_by(AuditEvent.event_type)
        )).all()

    counts = {name: n for name, n in rows}
    attempted = counts.get("remediation.executing", 0)
    applied = counts.get("remediation.applied", 0)
    rolled_back = counts.get("remediation.rolled_back", 0)
    succeeded = max(applied - rolled_back, 0)

    return {
        "attempted": attempted,
        "patch_applied": applied,
        "patch_rejected": counts.get("remediation.failed", 0),
        "rolled_back_after_verification": rolled_back,
        "verified_success": succeeded,
        "patch_apply_rate": round(applied / attempted, 3) if attempted else None,
        "remediation_success_rate": round(succeeded / attempted, 3) if attempted else None,
    }


def aggregate(runs: list[dict]) -> dict:
    """Mean and range for each numeric metric across repeated runs."""
    keys = [
        "root_cause_accuracy", "evidence_recall", "evidence_grounded_diagnosis_rate",
        "hypothesis_verification_rate", "investigation_success_rate",
        "tool_call_efficiency", "mean_tool_calls", "mean_tokens",
    ]
    out: dict[str, Any] = {"repeats": len(runs)}
    for k in keys:
        vals = [r[k] for r in runs if r.get(k) is not None]
        out[k] = {
            "mean": round(sum(vals) / len(vals), 3),
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
        } if vals else None
    lat = [r["latency_seconds"]["mean"] for r in runs if r.get("latency_seconds")]
    out["latency_seconds"] = {
        "mean": round(sum(lat) / len(lat), 1), "min": round(min(lat), 1), "max": round(max(lat), 1)
    } if lat else None
    return out


async def run_benchmark_evaluation(
    incident_ids: list[str] | None = None, repeat: int = 1
) -> None:
    from app.llm.usage import investigation_context  # noqa: F401  (context set per run)

    selected = [
        i for i in BENCHMARK_INCIDENTS
        if (incident_ids and i["id"] in incident_ids)
        or (not incident_ids and i["id"] in SUPPORTED_INCIDENTS)
    ]

    print("=" * 74)
    print("AEIP BENCHMARK EVALUATION (live runs)")
    print("=" * 74)
    skipped = [i["id"] for i in BENCHMARK_INCIDENTS if i not in selected]
    if skipped:
        print(f"Skipped (no seeded corpus): {', '.join(skipped)}")
    print(f"Running {len(selected)} incident(s). Each executes the full agent graph.")
    print("-" * 74)

    results = []
    per_run_summaries = []
    for rep in range(1, repeat + 1):
        run_results = []
        for idx, inc in enumerate(selected, start=1):
            label = f"[run {rep}/{repeat}][{idx:02d}/{len(selected)}]"
            print(f"{label} {inc['id']} — {inc['name']} ...", flush=True)
            r = await evaluate_incident(inc)
            r["repeat"] = rep
            run_results.append(r)
            print(
                f"       status={r['status']} rca={r['rca_accuracy']:.2f} "
                f"ev_recall={r['evidence_recall']:.2f} findings={r['findings_count']} "
                f"tools={r['tool_calls_used']} tokens={r['tokens_used']} "
                f"{r['elapsed_seconds']}s",
                flush=True,
            )
        results.extend(run_results)
        per_run_summaries.append(summarise(run_results))

    summary = summarise(results)
    if repeat > 1:
        # LLM output varies between runs; a single run is not a measurement.
        summary["across_runs"] = aggregate(per_run_summaries)
    summary["remediation"] = await remediation_stats()
    print("-" * 74)
    for k, v in summary.items():
        print(f"  {k:36} {v}")
    print("=" * 74)

    # Live runs go to their own file so the reference figures in
    # evaluation_results.json are never overwritten by a measurement.
    out = os.path.join(
        os.path.dirname(__file__), "..", "evaluation_results.measured.json"
    )
    with open(out, "w") as f:
        json.dump({
            "generated_at": datetime.now(UTC).isoformat(),
            "measured": True,
            "summary": summary,
            "results": results,
        }, f, indent=2)
    print(f"Report written to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the AEIP benchmark evaluation.")
    parser.add_argument("--incident", action="append", help="Incident id (repeatable)")
    parser.add_argument("--all", action="store_true", help="Run every incident, including unseeded ones")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat the suite N times and aggregate")
    args = parser.parse_args()

    ids = args.incident
    if args.all:
        ids = [i["id"] for i in BENCHMARK_INCIDENTS]

    asyncio.run(run_benchmark_evaluation(ids, repeat=max(1, args.repeat)))
