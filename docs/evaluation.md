# Evaluation Framework — Autonomous Engineering Intelligence Platform

## 1. Objectives

The evaluation framework rigorously assesses the platform against a dataset of synthetic and historical engineering incidents. It validates that the autonomous agents correctly identify root causes, assemble necessary evidence, reject false correlations, and produce correct remediations without wasting tool calls or exceeding token budgets.

---

## 2. Benchmark Incidents

The platform includes a benchmark dataset of 10 standard software incidents with known ground-truth:

| Incident ID | Incident Name | Primary Domain | Root Cause Ground Truth |
| :--- | :--- | :--- | :--- |
| `INC-001` | Database Regression | Database / ORM | Missing index and unindexed N+1 query in checkout inventory lookup introduced in commit diff. |
| `INC-002` | Memory Leak | Runtime / Lifecycle | Unbounded global cache dictionary accumulating unbounded event listener callbacks. |
| `INC-003` | Bad Configuration | DevOps / Config | Environment variable `MAX_CONNECTIONS` set to 5 instead of 500 in deployment manifest. |
| `INC-004` | Dependency Incompatibility | Packaging / Libs | Upgraded serialization library breaking backward-compatible JSON schema deserialization. |
| `INC-005` | API Contract Mismatch | API / Gateway | Downstream billing service expects `order_id` (string), checkout sends `order_id` (integer). |
| `INC-006` | Deployment Regression | Git / Diff | Duplicate HTTP middleware interceptor causing redundant round-trips. |
| `INC-007` | Slow Downstream Service | Network / Timeout | Missing socket read timeout on third-party address verification API, causing worker thread pool exhaustion. |
| `INC-008` | Unhandled Exception | Logic / Error Handling | Null-pointer / AttributeError on optional customer billing metadata during guest checkout. |
| `INC-009` | Race Condition | Concurrency | Concurrent balance deduction without row-level lock (`SELECT ... FOR UPDATE`). |
| `INC-010` | Missing Environment Variable | Env / Secrets | Production container missing `STRIPE_WEBHOOK_SECRET`, silently falling back to 500 error handlers. |

---

## 3. Evaluation Metrics

Every benchmark run computes:

1. **Root Cause Accuracy (RCA)**: Binary (0 or 1) + Semantic similarity to ground-truth root cause.
2. **Evidence Precision & Recall**: Proportion of true causal evidence gathered vs irrelevant telemetry queried.
3. **Hypothesis Quality**: Did the system formulate the correct hypothesis? Was the wrong hypothesis appropriately rejected by the Critic?
4. **Tool Efficiency**: Number of tool calls executed vs minimum theoretical tool calls needed.
5. **Token Consumption & Cost**: Total input/output tokens used and estimated cost in USD.
6. **Time to Resolution (TTR)**: Wall-clock execution time from investigation start to final report generation.
7. **Patch Correctness**: For remediation runs, did the proposed patch compile, pass automated tests, and fix the regression without introducing new failures?

---

## 4. Running Benchmarks

```bash
# Run the complete evaluation suite
python scripts/run_evaluation.py --all

# Run a specific incident evaluation
python scripts/run_evaluation.py --incident INC-001

# Export evaluation metrics to JSON and Markdown summary
python scripts/run_evaluation.py --export-report ./evaluation_results.json
```
