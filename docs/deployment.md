# Deployment Guide — Autonomous Engineering Intelligence Platform

## 1. Local Development (Docker Compose)

For local development and staging verification, bring up the entire multi-container topology using Docker Compose:

```bash
# 1. Clone repository and initialize environment variables
cp .env.example .env
# Configure your LLM_PROVIDER and API keys in .env

# 2. Start PostgreSQL, Redis, Qdrant, MinIO, Prometheus, Grafana, OpenTelemetry
docker-compose up -d postgres redis qdrant minio otel-collector prometheus grafana

# 3. Apply database migrations
cd backend
alembic upgrade head

# 4. Seed initial database records & demo repository
python ../scripts/seed_database.py
python ../scripts/seed_demo_repo.py

# 5. Start Backend API & Next.js Frontend
# Terminal 1:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Terminal 2:
cd ../frontend && npm install && npm run dev
```

---

## 2. Production Topology (Kubernetes / Cloud)

In production environments, control plane and execution plane components are decoupled for scale and resilience:

```
                      [ Ingress / Cloudflare ]
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       [ Frontend (Next.js) ]           [ Backend API (FastAPI) ]
                 │                               │
                 │                     ┌─────────┴─────────┐
                 │                     ▼                   ▼
                 │            [ Managed Postgres ]  [ Managed Redis ]
                 │                     ▲                   ▲
                 │                     └─────────┬─────────┘
                 │                               │
                 │                     [ Worker Agents (LangGraph) ]
                 │                               │
                 │                     ┌─────────┴─────────┐
                 │                     ▼                   ▼
                 │             [ Qdrant Cluster ]   [ S3 Storage ]
                 │
                 └────────────> SSE Stream for Live Dashboards
```

---

## 3. Sandboxed Worker Nodes

In high-concurrency environments:
- Agent nodes execute within dedicated Kubernetes worker pods.
- Code execution tools interface with an isolated Docker socket or Firecracker microVM runner with strict isolation (`security_opt`, read-only root, memory/CPU quotas).
- Outbound network egress from worker pods is disabled by default to prevent data exfiltration.
