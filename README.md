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
curl -X POST http://localhost:8000/api/v1/investigations \
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
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "audit",
    "project_id": "<project-uuid>",
    "objective": "Assess the reliability of the checkout service before deployment"
  }'
```

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
