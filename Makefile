# FinFlow — developer convenience targets.
# Requires GNU Make, Docker (for container targets), uv and npm.

PY := uv run --project backend
FRONT := cd frontend

.PHONY: help install dev dev-api dev-front up down logs test lint migrate backup restore

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

dev-api: ## Run the FastAPI backend with hot reload (expects dev compose)
	$(PY) uvicorn app.main:app --reload --port 8000

dev-front: ## Run the Vite dev server
	cd frontend && npm run dev

dev: ## Start local infrastructure (postgres + redis) in Docker
	docker compose -f docker-compose.dev.yml up -d

up: ## Start the full production stack
	docker compose up -d --build

down: ## Stop the production stack
	docker compose down

logs: ## Tail logs of all services
	docker compose logs -f --tail=100

test: ## Run backend tests
	$(PY) pytest

lint: ## Lint and format-check backend and frontend
	$(PY) ruff check backend/app backend/tests
	$(PY) black --check backend/app backend/tests
	$(PY) mypy backend/app
	cd frontend && npm run lint && npm run type-check

migrate: ## Apply Alembic migrations (defined in TASK-003)
	$(PY) alembic upgrade head

backup: ## Back up PostgreSQL and uploads (defined in TASK-058)
	./scripts/backup.sh

restore: ## Restore a backup (defined in TASK-058)
	./scripts/restore.sh
