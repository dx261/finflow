# FinFlow — Personal Treasury Management System

**FinFlow — 个人多账户资金管理与现金流规划平台**

FinFlow is a personal, long-lived treasury management system. It unifies
multiple bank accounts, imports and standardizes heterogeneous bank
statements, plans payments, recommends how to fund them, virtually reserves
funds, and reconciles planned payments against real bank transactions.

> **FinFlow manages information, planning, reconciliation and financial
> decision support. FinFlow never moves real money.**

All real-world money operations (paying, transferring, freezing) are
performed 100% manually by the user at their bank. FinFlow's job ends at
providing a recommendation and later verifying the result.

## Safety Boundary

The following are **explicitly forbidden** in this codebase:

- Real-bank auto-login, credential storage, SMS/OTP handling
- USB Key control, bank web RPA, auto-transfer, auto-payment
- Modifying real bank funds, bypassing bank security, scraping private APIs

## Architecture

Modular monolith + async worker:

```text
Browser → Nginx → FastAPI API → PostgreSQL / Redis → Celery Worker
```

| Layer | Technology |
| --- | --- |
| Frontend | Vue 3 · TypeScript · Vite · Element Plus · Pinia · ECharts |
| Backend | Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic |
| Async | Celery · Redis (broker, cache, locks) |
| Data | PostgreSQL 16 · Redis 7 |
| Money | `Decimal` / `NUMERIC(18,2)` — floats are forbidden for amounts |

## Repository Layout

```text
backend/     FastAPI application (uv-managed)
frontend/    Vue 3 + TypeScript application (Vite)
nginx/       Reverse proxy and static file server
sample-data/ Sample bank statement files and demo data
scripts/     Utility scripts (backup, demo data, ...)
```

## Quick Start (Development)

Requirements: [uv](https://docs.astral.sh/uv/), Node.js 20+, Docker.

```bash
# 1. Start local infrastructure (PostgreSQL + Redis)
docker compose -f docker-compose.dev.yml up -d

# 2. Install dependencies
cd backend && uv sync
cd ../frontend && npm install

# 3. Run the backend (http://localhost:8000, docs at /docs)
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 4. Run the frontend (http://localhost:5173)
cd frontend && npm run dev
```

Health check: `GET http://localhost:8000/api/v1/health`

## Production

```bash
cp .env.example .env     # adjust secrets
docker compose up -d --build
```

Only Nginx (ports 80/443) is exposed externally.

## Development Status

Implemented incrementally following `CODING_PLAN.md`, one task at a time.

- **TASK-001 Repository Bootstrap** — DONE
- **TASK-003 Database Infrastructure** — DONE (PostgreSQL via asyncpg in
  production; tests run on SQLite so no server is required locally)
- **TASK-006 FastAPI Core** — DONE (unified error envelope
  `code`/`message`/`trace_id`, X-Request-ID propagation, versioned router
  aggregation)
- **TASK-004 Redis Infrastructure** — DONE (async redis-py client wired
  into the health probe; Celery broker/cache/locks later)
- **TASK-008 Authentication** — DONE (users table migration on PostgreSQL,
  bcrypt password hashing, JWT access/refresh tokens, OWNER/VIEWER roles,
  register/login/refresh/me endpoints)
- **TASK-009 Bank Model** — DONE (banks catalog with seeded defaults,
  OWNER-only writes, auth-protected reads)
- **TASK-010 Account Model** — DONE (accounts table on PostgreSQL with
  NUMERIC(18,2) money, the three balance concepts with live-computed
  `planning_available`, OWNER-only writes)
- **TASK-011 Account Balance Snapshot** — DONE (point-in-time balance
  records for trends, sources STATEMENT/MANUAL/IMPORT)
- **TASK-012 Audit Log** — DONE (immutable audit trail with before/after
  JSON state and trace IDs; wired into account create/update; OWNER-only
  query endpoint)
- **TASK-019/015/016/017/018 Statement Parsing** — DONE (normalize_text,
  generic file loader, floating anchor detection, dynamic table
  detection, ICBC/CMB/generic parsers with Decimal money and direction
  resolution)
- **TASK-020/021/022** — DONE (transaction fingerprint dedup, rule-based
  category engine, internal transfer detection)

## Tooling

| Backend | Frontend |
| --- | --- |
| ruff · black · mypy · pytest | ESLint · Prettier · vue-tsc |
