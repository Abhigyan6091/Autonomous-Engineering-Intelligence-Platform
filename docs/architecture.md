# Architecture — Autonomous Engineering Intelligence Platform

## 1. Purpose

The Autonomous Engineering Intelligence Platform (AEIP) is a production-grade AI system designed to function as an autonomous Software Reliability Engineer (SRE). It investigates incidents, audits repositories, forms evidence-backed hypotheses, and recommends remediations with full human oversight and auditability.

The system is NOT:
- A generic chatbot
- A simple LLM-over-tools pipeline
- A hard-coded investigation script

The system IS:
- A multi-agent orchestration system with genuine planning and dynamic decomposition
- A durable workflow engine with persistent state and checkpointing
- An evidence-driven reasoning system with formal hypothesis lifecycle management
- A production-grade engineering tool with security controls, sandboxing, and human approval gates

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                               │
│                    Next.js Dashboard (SSE streaming)                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS / WSS
┌──────────────────────────────▼──────────────────────────────────────┐
│                         API GATEWAY                                  │
│              FastAPI + JWT Auth + Rate Limiting                      │
│     /health  /investigations  /findings  /approvals  /events         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Control Plane   │ │   Persistence    │ │  Event Bus       │
│                  │ │                  │ │                  │
│  Investigation   │ │  PostgreSQL      │ │  Redis Streams   │
│  Manager         │ │  (durable state) │ │  (SSE events)    │
│                  │ │                  │ │                  │
│  Project Service │ │  Alembic         │ │  Rate Limiter    │
│  Approval Service│ │  migrations      │ │                  │
│  Report Service  │ │                  │ │                  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       EXECUTION PLANE                                │
│                                                                      │
│   LangGraph StateGraph (PostgreSQL-checkpointed)                    │
│                                                                      │
│   ┌──────────┐  ┌──────────┐  ┌─────────────────────────────────┐  │
│   │Supervisor│→ │ Planner  │→ │     Dynamic Task Graph          │  │
│   └──────────┘  └──────────┘  │  Send(code) ──┐                 │  │
│                                │  Send(log)    ├→ evidence_merge │  │
│                                │  Send(test)   │                 │  │
│                                │  Send(metrics)┘                 │  │
│                                └─────────────────────────────────┘  │
│                                                                      │
│   ┌───────────────────────────────────────────────────────────────┐ │
│   │                  Specialized Agents                            │ │
│   │  Code │ Test │ Log │ Metrics │ Research │ Hypothesis │ Critic │ │
│   └────────────────────────────┬──────────────────────────────────┘ │
│                                │                                     │
│                      Tool Gateway (All tools pass through here)     │
│                      Auth → Risk → Validate → Sandbox → Audit      │
└──────────────────────────────────────────────────────────────────────┘
          │
    ┌─────┼──────────────────────────────────┐
    ▼     ▼                 ▼                ▼
┌───────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐
│ Qdrant│ │  MinIO   │ │  Git   │ │   Sandbox    │
│(vector│ │(artifacts│ │  Repos │ │  (Docker /   │
│ store)│ │& reports)│ │        │ │  subprocess) │
└───────┘ └──────────┘ └────────┘ └──────────────┘
```

---

## 3. Control Plane vs Execution Plane

### Control Plane
The control plane handles all durable business concerns. It is deterministic Python code — no LLMs involved.

Responsibilities:
- User authentication and authorization
- Project and repository management
- Investigation lifecycle management (create, start, pause, complete)
- Human approval workflow
- Report generation and export
- Audit event persistence
- Cost tracking
- Rate limiting

Key components:
- `FastAPI` application with versioned REST API
- `InvestigationService` — manages investigation state machine
- `ApprovalService` — manages human approval gates
- `ReportService` — generates structured investigation reports
- `AuditService` — records immutable audit events

### Execution Plane
The execution plane handles all dynamic, AI-driven reasoning. This is where LangGraph, agents, and tools live.

Responsibilities:
- LangGraph workflow execution
- Agent task assignment and routing
- LLM calls (planning, reasoning, analysis)
- Tool execution via the Tool Gateway
- Evidence gathering and correlation
- Hypothesis lifecycle management
- Self-criticism and retry logic

Key components:
- `LangGraph StateGraph` — the primary workflow engine
- `Supervisor Agent` — coordinates the investigation
- `Specialized Agents` — focused analytical agents
- `Tool Gateway` — secure, audited tool execution layer
- `Sandbox` — isolated code execution

---

## 4. Data Architecture

### PostgreSQL (durable state)
All business-critical data lives here:
- Users, Projects, Repositories
- Investigations, Tasks, Findings
- Evidence, Hypotheses, Approvals
- Tool Executions, Audit Events, LLM Usage

This data must survive process restarts. PostgreSQL is also used as the LangGraph checkpoint store.

### Redis (transient coordination)
Used for:
- Background job queues (investigation execution)
- SSE event streaming (investigation progress events)
- Rate limiting counters
- Short-lived agent state cache
- Session tokens

NOT used for durable business state.

### Qdrant (semantic retrieval)
Used for:
- Repository documentation chunks
- Architecture documents and runbooks
- Previous investigation knowledge base
- Source code semantic search
- API documentation

### MinIO / S3 (artifact storage)
Used for:
- Generated investigation reports (JSON, Markdown)
- Large log files
- Patch artifacts
- Test output artifacts
- Sandbox execution artifacts

---

## 5. LLM Architecture

### Provider Abstraction
All LLM calls go through a `ModelFactory` that returns a `BaseChatModel` instance. The provider is determined by `LLM_PROVIDER` environment variable.

```python
# Configuration
LLM_PROVIDER = "openai"   # or: anthropic | gemini | ollama
LLM_MODEL = "gpt-4o"
LLM_FAST_MODEL = "gpt-4o-mini"
```

Supported providers:
- **OpenAI** — `langchain-openai` (`ChatOpenAI`)
- **Anthropic** — `langchain-anthropic` (`ChatAnthropic`)
- **Google Gemini** — `langchain-google-genai` (`ChatGoogleGenerativeAI`)
- **Ollama** — `langchain-ollama` (`ChatOllama`)

### Model Selection Strategy
Two model tiers:
- **Primary model** — used for complex reasoning, planning, hypothesis generation, critic
- **Fast model** — used for classification, routing decisions, quick analysis

### Structured Output
All LLM outputs use Pydantic schemas via `.with_structured_output()`. The system never parses free-form text for structured decisions.

---

## 6. Security Architecture

### Defense in Depth

1. **API Layer** — JWT authentication, rate limiting, input validation
2. **Tool Gateway** — authorization, risk assessment, input sanitization
3. **Sandbox** — isolated Docker container with CPU/memory/network limits
4. **Prompt Injection Defense** — repository content is always wrapped as data, never injected as instructions
5. **Secret Redaction** — all content passes through a redaction layer before reaching the LLM
6. **Audit Logging** — every consequential action creates an immutable audit event

### Tool Risk Classification
Tools are classified into risk levels:
- `low` — read-only operations, no side effects
- `medium` — sandbox execution, read-only database queries
- `high` — write operations (patches, branches) — require human approval
- `critical` — deployment operations — disabled by default

---

## 7. Observability Architecture

Every request and investigation action carries:
- `trace_id` — OpenTelemetry trace
- `investigation_id` — business context
- `task_id` — current task
- `agent_id` — executing agent
- `tool_execution_id` — specific tool call

Metrics exported to Prometheus:
- `investigation_duration_seconds`
- `agent_latency_seconds`
- `tool_call_latency_seconds`
- `llm_call_latency_seconds`
- `tool_failures_total`
- `agent_retries_total`
- `llm_tokens_total`
- `investigation_completed_total`
- `finding_count`
- `approval_pending_total`
- `estimated_cost_usd`

---

## 8. Failure Handling

The system is designed to be failure-tolerant:

- **LLM failures** — exponential backoff retry (max 3 attempts), then fallback to simpler model
- **Tool failures** — timeout + retry (max 2 attempts for transient errors), then error evidence
- **Database failures** — connection pool retry, circuit breaker
- **Sandbox failures** — timeout enforcement, container cleanup
- **Budget exceeded** — investigation transitions to `budget_exceeded` state, partial report generated
- **Loop detection** — maximum retry count per node (3), maximum investigation duration (1 hour)

---

## 9. Key Design Decisions

### ADR-001: LangGraph over custom orchestration
**Decision**: Use LangGraph as the primary orchestration engine.
**Rationale**: LangGraph provides built-in support for stateful graphs, persistent checkpointing, parallel execution via Send, and human-in-the-loop interrupts. Building a comparable system from scratch would require significant engineering effort.
**Trade-off**: Dependency on LangGraph API stability.

### ADR-002: PostgreSQL for LangGraph checkpoints
**Decision**: Use PostgreSQL (not SQLite or memory) as the LangGraph checkpoint backend.
**Rationale**: Investigations must survive process restarts and be resumable. PostgreSQL provides the durability guarantees required for production.
**Trade-off**: Requires PostgreSQL in all environments (mitigated by SQLite dev fallback).

### ADR-003: Tool Gateway as a mandatory intermediary
**Decision**: All tool calls from agents must pass through the Tool Gateway.
**Rationale**: The Tool Gateway is the single point of enforcement for authorization, validation, sandboxing, rate limiting, and audit logging. Agents should not have direct access to tools.
**Trade-off**: Added latency per tool call (~1-5ms).

### ADR-004: Structured LLM outputs everywhere
**Decision**: All LLM responses that produce structured data use `with_structured_output()`.
**Rationale**: Prevents hallucinated malformed responses from breaking downstream logic. Provides type safety.
**Trade-off**: Slightly higher token usage for schema descriptions in prompts.

### ADR-005: Human approval as a LangGraph interrupt
**Decision**: Human approval gates are implemented as LangGraph interrupt points.
**Rationale**: This naturally pauses the graph, persists state to PostgreSQL, and waits for the API to receive human input before resuming.
**Trade-off**: Requires careful state design to ensure resumability.

### ADR-006: Confidence as evidence-backed, not LLM-asserted
**Decision**: Hypothesis confidence scores are computed from structured evidence counts and quality, not from LLM self-assessment.
**Rationale**: LLMs tend to assert high confidence even without strong evidence. A deterministic confidence computation prevents hallucinated certainty.
**Trade-off**: The confidence formula requires tuning.
