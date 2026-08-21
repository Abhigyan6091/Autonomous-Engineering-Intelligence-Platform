# =============================================================================
# Autonomous Engineering Intelligence Platform — Makefile
# =============================================================================

.PHONY: help dev dev-backend dev-frontend test lint typecheck migrate \
        seed evaluate docker-up docker-down docker-logs clean install

PYTHON := python
PIP := pip
ROOT := $(shell pwd)
BACKEND_DIR := $(ROOT)/backend
FRONTEND_DIR := $(ROOT)/frontend

# Colors
BOLD := \033[1m
RESET := \033[0m
GREEN := \033[32m
YELLOW := \033[33m
CYAN := \033[36m

help: ## Show this help message
	@echo ""
	@echo "$(BOLD)Autonomous Engineering Intelligence Platform$(RESET)"
	@echo ""
	@echo "$(CYAN)Usage:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ============================================================
# Development
# ============================================================

install: ## Install all Python dependencies
	$(PIP) install -e ".[dev]"
	@echo "$(GREEN)✓ Dependencies installed$(RESET)"

dev-backend: ## Start the FastAPI backend in development mode
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start the Next.js frontend in development mode
	cd $(FRONTEND_DIR) && npm run dev

dev: ## Start both backend and frontend (requires tmux or run in separate terminals)
	@echo "$(YELLOW)Run these in separate terminals:$(RESET)"
	@echo "  make dev-backend"
	@echo "  make dev-frontend"

# ============================================================
# Database
# ============================================================

migrate: ## Run Alembic database migrations
	cd $(BACKEND_DIR) && alembic upgrade head
	@echo "$(GREEN)✓ Migrations applied$(RESET)"

migrate-create: ## Create a new migration (usage: make migrate-create MSG="description")
	cd $(BACKEND_DIR) && alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Roll back the last migration
	cd $(BACKEND_DIR) && alembic downgrade -1

migrate-history: ## Show migration history
	cd $(BACKEND_DIR) && alembic history --verbose

seed: ## Seed the database with demo data
	cd $(BACKEND_DIR) && $(PYTHON) ../scripts/seed_database.py

seed-demo: ## Create the demo repository and incident data
	cd $(ROOT) && $(PYTHON) scripts/seed_demo_repo.py

# ============================================================
# Testing
# ============================================================

test: ## Run all tests
	cd $(BACKEND_DIR) && pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	cd $(BACKEND_DIR) && pytest tests/unit/ -v

test-integration: ## Run integration tests (requires running services)
	cd $(BACKEND_DIR) && pytest tests/integration/ -v

test-agents: ## Run agent tests
	cd $(BACKEND_DIR) && pytest tests/agents/ -v

test-tools: ## Run tool tests
	cd $(BACKEND_DIR) && pytest tests/tools/ -v

test-cov: ## Run tests with coverage report
	cd $(BACKEND_DIR) && pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# ============================================================
# Code Quality
# ============================================================

lint: ## Run Ruff linter
	ruff check $(BACKEND_DIR)/app $(BACKEND_DIR)/tests
	@echo "$(GREEN)✓ Lint passed$(RESET)"

lint-fix: ## Run Ruff linter with auto-fix
	ruff check --fix $(BACKEND_DIR)/app $(BACKEND_DIR)/tests

format: ## Format code with Ruff
	ruff format $(BACKEND_DIR)/app $(BACKEND_DIR)/tests

typecheck: ## Run mypy type checker
	mypy $(BACKEND_DIR)/app --ignore-missing-imports
	@echo "$(GREEN)✓ Type check passed$(RESET)"

security: ## Run Bandit security scanner
	bandit -r $(BACKEND_DIR)/app -ll -q
	@echo "$(GREEN)✓ Security scan passed$(RESET)"

check: lint typecheck security ## Run all code quality checks

# ============================================================
# Docker
# ============================================================

docker-up: ## Start all Docker services
	docker-compose up -d
	@echo "$(GREEN)✓ Services started$(RESET)"
	@echo "  Backend:    http://localhost:8000"
	@echo "  Frontend:   http://localhost:3000"
	@echo "  Grafana:    http://localhost:3001"
	@echo "  MinIO:      http://localhost:9001"
	@echo "  Prometheus: http://localhost:9090"

docker-infra: ## Start only infrastructure services (postgres, redis, qdrant, minio)
	docker-compose up -d postgres redis qdrant minio
	@echo "$(GREEN)✓ Infrastructure started$(RESET)"

docker-down: ## Stop all Docker services
	docker-compose down

docker-clean: ## Stop services and remove volumes
	docker-compose down -v
	@echo "$(YELLOW)⚠ Volumes removed$(RESET)"

docker-logs: ## Tail logs for all services
	docker-compose logs -f

docker-logs-backend: ## Tail backend logs
	docker-compose logs -f backend

docker-build: ## Build all Docker images
	docker-compose build

# ============================================================
# Evaluation
# ============================================================

evaluate: ## Run the evaluation benchmark
	$(PYTHON) scripts/run_evaluation.py

ingest: ## Ingest a repository (usage: make ingest REPO_PATH=/path/to/repo PROJECT_ID=uuid)
	$(PYTHON) scripts/ingest_repository.py --repo-path $(REPO_PATH) --project-id $(PROJECT_ID)

# ============================================================
# Utilities
# ============================================================

clean: ## Clean build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(RESET)"

health: ## Check health of all running services
	@echo "Backend health:"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "Backend not running"

docs: ## Open the documentation
	@echo "Architecture:   docs/architecture.md"
	@echo "Agent Design:   docs/agent-design.md"
	@echo "Workflow:       docs/workflow-design.md"
	@echo "Security:       docs/security.md"
	@echo "Evaluation:     docs/evaluation.md"

version: ## Show versions of key dependencies
	@$(PYTHON) --version
	@node --version
	@git --version
	@echo "FastAPI: $(shell $(PYTHON) -c 'import fastapi; print(fastapi.__version__)' 2>/dev/null || echo 'not installed')"
	@echo "LangGraph: $(shell $(PYTHON) -c 'import langgraph; print(langgraph.__version__)' 2>/dev/null || echo 'not installed')"
