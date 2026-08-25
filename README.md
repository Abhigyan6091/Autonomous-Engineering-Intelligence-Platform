# Autonomous Engineering Intelligence Platform

> An AI-powered Software Reliability Engineering system that autonomously investigates incidents, audits repositories, forms evidence-backed hypotheses, and recommends remediations with full auditability.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

## Overview

The **Autonomous Engineering Intelligence Platform (AEIP)** behaves like an AI Software Reliability Engineer. Given a reported incident or an audit objective, it:

1. **Plans** an investigation autonomously — no manual step specification required
2. **Executes** specialized agents in parallel (code, log, metrics, test, research)
3. **Forms and tests hypotheses** backed by gathered evidence
4. **Challenges its own findings** via a dedicated Critic agent
5. **Recommends remediations** with full evidence traceability
6. **Requires human approval** before any consequential action
7. **Produces an auditable report** with complete provenance

---

## Architecture

```
Client (Next.js Dashboard)
        │
        ▼
API Gateway (FastAPI)
        │
        ▼
Investigation Manager
        │
        ▼
LangGraph Orchestrator
        │
  ┌─────┴──────────────────────────┐
  │         Specialized Agents      │
  │  Supervisor │ Planner │ Code    │
  │  Test │ Log │ Metrics │ Research│
  │  Hypothesis │ Critic │ Remediation│
  └────────────┬───────────────────┘
               │
         Tool Gateway
               │
    ┌──────────┼──────────┐
    │          │          │
   Git      Sandbox    Retrieval
  Tools    Execution   (Qdrant)
```

See [docs/architecture.md](docs/architecture.md) for the full architecture document.

---

## Quick Start

### Fastest path

```bash
./start.sh            # start backend + frontend
./start.sh status     # what is running, and where
./start.sh stop       # shut both down
```

`start.sh` picks free ports automatically (the default `8000` is often taken by
another service), points the frontend at whichever port the backend got, waits
for `/health`, and writes logs to `.run/`. Override with `AEIP_BACKEND_PORT` /
`AEIP_FRONTEND_PORT`.

It expects `.venv` and a configured `.env`; the manual steps below cover
first-time setup.

### Prerequisites

- Docker Desktop
- Python 3.12+
- Node.js 18+
- An LLM API key (OpenAI, Anthropic, or Gemini) OR local Ollama

### 1. Clone and configure

```bash
git clone <repo>
cd autonomous-engineering-intelligence
cp .env.example .env
# Edit .env and set your LLM_PROVIDER and API key
```

### 2. Start infrastructure

```bash
docker-compose up -d postgres redis qdrant minio
```

### 3. Install Python dependencies

```bash
pip install -e ".[dev]"
```

### 4. Run database migrations

```bash
make migrate
```

### 5. Start the backend

```bash
make dev-backend
```

### 6. Start the frontend

```bash
make dev-frontend
```

### 7. Open the dashboard

Navigate to [http://localhost:3000](http://localhost:3000)

---

## Investigation Modes

### Incident Investigation

```bash
curl -X POST "${AEIP_API:-http://localhost:8000}/api/v1/investigations" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "incident",
    "project_id": "<project-uuid>",
    "objective": "Checkout API p95 latency increased by 35% after deployment v2.8.1",
    "metadata": {
      "time_window": {"start": "2024-01-15T10:00:00Z", "end": "2024-01-15T14:00:00Z"},
      "severity": "high"
    }
  }'
```

### Repository Audit

```bash
curl -X POST "${AEIP_API:-http://localhost:8000}/api/v1/investigations" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "audit",
    "project_id": "<project-uuid>",
    "objective": "Assess the reliability of the checkout service before deployment"
  }'
```

---

## Key Capabilities

| Capability | Description |
|------------|-------------|
| **Parallel agent execution** | The planner fans work out to specialist agents (code, log, metrics, test, research) that run concurrently and merge their evidence. |
| **Durable investigations** | Graph state is checkpointed, so an investigation survives a backend restart and resumes exactly where it paused. |
| **Human approval gate** | Consequential actions pause the workflow. Approving or rejecting resumes the paused graph from its checkpoint. |
| **Verified remediation** | An approved patch is applied on an isolated branch, verified against the test suite, and rolled back automatically if verification fails. |
| **Repository targeting** | Investigate any GitHub URL (cloned on demand) or a local folder, selected per investigation. |
| **Live telemetry** | Server-Sent Events stream every agent start, tool call, evidence addition, and decision as it happens. |
| **Budget accounting** | Token consumption and tool calls are metered per investigation against configurable ceilings. |
| **Evidence provenance** | Every finding cites the specific evidence records supporting it. |

---

## Reliability and Safety

The remediation path is designed so that a bad patch cannot damage a working tree:

- **Isolated by construction** — patches are applied on a dedicated `aeip/remediation/*` branch, never on the checked-out branch.
- **Validated before applying** — a dry run rejects a malformed patch before any file is touched.
- **Automatically rolled back** — if the test suite fails after applying, the branch is deleted and the workspace is restored.
- **Refuses ambiguous targets** — a workspace without its own `.git` is rejected rather than committing to a parent repository.
- **Fails closed on approval** — only an explicit approval proceeds; any other decision is treated as a rejection.

Findings are grounded by validation: evidence identifiers cited by the model are
resolved against real records, and unknown references are discarded rather than
reported.

---

## Performance

### Benchmark Suite

Scored across the 10-incident benchmark dataset (`docs/evaluation.md`), which
pairs each incident with a documented ground-truth root cause:

| Metric | Result |
|--------|--------|
| **Root cause accuracy** | **92.3%** |
| Benchmark incidents | 10 |
| Suite status | All passing |

Figures are held in `evaluation_results.json`.

### Live Runs

Live runs of the `INC-001` benchmark (database latency regression), executed end
to end against the seeded demo repository with a local Ollama model. Figures are
the mean of 3 repeats:

| Metric | Result |
|--------|--------|
| Investigation success rate | **100%** |
| Evidence-grounded diagnosis rate | **100%** |
| Hypothesis verification rate | **100%** |
| Evidence recall (ground-truth signals retrieved) | **0.75** |
| End-to-end latency | **~186 s** |
| Tokens per investigation | **~12,400** |
| Tool calls per investigation | **~9** |
| Backend test suite | **22 / 22 passing** |

Reproduce with:

```bash
python scripts/run_evaluation.py --repeat 3
```

Live results are written to `evaluation_results.measured.json`.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System architecture and design decisions |
| [Agent Design](docs/agent-design.md) | Specialized agent roles and responsibilities |
| [Workflow Design](docs/workflow-design.md) | LangGraph state machine and investigation workflow |
| [Security](docs/security.md) | Security model, threat mitigations, sandbox design |
| [Threat Model](docs/threat-model.md) | Detailed threat analysis |
| [Evaluation](docs/evaluation.md) | Benchmark framework and synthetic incidents |
| [Deployment](docs/deployment.md) | Production deployment guide |

---

## Development

```bash
make help          # Show all available commands
make test          # Run test suite
make lint          # Run linter (Ruff)
make typecheck     # Run type checker (mypy)
make migrate       # Run database migrations
make seed          # Seed demo data
make evaluate      # Run evaluation benchmark
```

Additional helpers:

```bash
./start.sh          # Start backend + frontend, selecting free ports automatically
./start.sh status   # Show what is running and where
./start.sh stop     # Stop both services

python scripts/seed_demo_repo.py             # Create the demo repository (with git history)
python scripts/run_evaluation.py --repeat 3  # Live benchmark, averaged over 3 runs
```

---

## Project Structure

```
autonomous-engineering-intelligence/
├── backend/         # FastAPI backend + agents + tools
├── frontend/        # Next.js dashboard
├── sandbox/         # Isolated execution environment
├── datasets/        # Synthetic incidents and evaluation data
├── scripts/         # Development and operational scripts
├── infra/           # Prometheus, Grafana, OTEL configs
├── docs/            # Architecture and design documentation
└── docker-compose.yml
```

---

## License

MIT License — see [LICENSE](LICENSE).
