.PHONY: dev backend frontend test migrate scaffold db-shell lint clean help

# ── Colors ────────────────────────────────────────────────────────────
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m

help: ## Show this help
	@echo ""
	@echo "$(CYAN)FlowForge$(RESET) — React Flow Alteryx Clone"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── Development ───────────────────────────────────────────────────────

dev: ## Start all services (frontend + backend)
	@echo "$(CYAN)Starting all services...$(RESET)"
	@trap 'kill 0' EXIT; \
		make backend & \
		make frontend & \
		wait

backend: ## Start FastAPI dev server
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend: ## Start Vite React dev server
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

# ── Database ──────────────────────────────────────────────────────────

migrate: ## Run Alembic migrations
	cd backend && alembic upgrade head

migrate-new: ## Create new migration (usage: make migrate-new msg="add workflows table")
	cd backend && alembic revision --autogenerate -m "$(msg)"

db-shell: ## Open PostgreSQL shell
	psql -h db -U flowforge -d flowforge

db-reset: ## Drop and recreate database (DESTRUCTIVE)
	@echo "$(CYAN)Resetting database...$(RESET)"
	psql -h db -U flowforge -d postgres -c "DROP DATABASE IF EXISTS flowforge;"
	psql -h db -U flowforge -d postgres -c "CREATE DATABASE flowforge;"
	cd backend && alembic upgrade head

# ── Testing ───────────────────────────────────────────────────────────

test: ## Run all tests
	cd backend && pytest -v --tb=short
	cd frontend && npm run test -- --run

test-back: ## Run backend tests only
	cd backend && pytest -v --tb=short --cov=app --cov-report=term-missing

test-front: ## Run frontend tests only
	cd frontend && npm run test -- --run

# ── Code Quality ──────────────────────────────────────────────────────

lint: ## Lint & format all code
	cd backend && ruff check . --fix && ruff format .
	cd frontend && npx eslint . --fix && npx prettier --write .

typecheck: ## Run type checking
	cd backend && mypy app/
	cd frontend && npx tsc --noEmit

# ── Scaffolding ───────────────────────────────────────────────────────

scaffold: ## Generate initial project structure
	@echo "$(CYAN)Scaffolding project...$(RESET)"
	@bash scripts/scaffold.sh
	@echo "$(GREEN)Done! Run 'make dev' to start.$(RESET)"

# ── Cleanup ───────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist backend/*.egg-info
