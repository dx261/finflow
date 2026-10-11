#!/usr/bin/env bash
# FinFlow 一键启动（开发模式）
#
#   1. LOCAL_DEMO=true: 项目内 SQLite；否则 Docker PostgreSQL + Redis
#   2. SQLite 建表及首次演示数据；或 PostgreSQL 数据库迁移
#   3. 后端 API        http://localhost:8000   （文档 /docs）
#   4. Celery worker   （账单导入等异步任务，前台不可少）
#   5. Celery beat     （周期付款计划生成）
#   6. 前端            http://localhost:5173
#
# 用法:
#   ./scripts/start-dev.sh            启动全部
#   ./scripts/start-dev.sh --no-front  跳过前端（只起后端+worker）
#   ./scripts/start-dev.sh --demo      再灌一份演示数据（demoowner / demo123456）
#   ./scripts/stop-dev.sh              停止脚本启动的进程
#
# 脚本是幂等的：已在跑的服务会跳过，不会重复拉起。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/.run"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$RUN_DIR" "$LOG_DIR"

USE_FRONT=1
USE_DEMO=0
for arg in "$@"; do
  case "$arg" in
    --no-front) USE_FRONT=0 ;;
    --demo)     USE_DEMO=1 ;;
    *) echo "未知参数: $arg" >&2; exit 1 ;;
  esac
done

say()  { printf '\033[1;34m[finflow]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[finflow]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[finflow]\033[0m %s\n' "$*" >&2; exit 1; }

port_ok()  { curl -sf -m 2 -o /dev/null "$1" >/dev/null 2>&1; }
alive()    { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }
# Windows 进程检测（按命令行特征），依赖 PowerShell 的 CIM
proc_exists() {
  powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '$1' } | Select-Object -First 1 -ExpandProperty ProcessId" 2>/dev/null \
    | grep -qE '^[0-9]+$'
}

start_bg() { # $1 名称  $2 pidfile  $3 日志  $4.. 命令
  local name="$1" pf="$2" log="$3"; shift 3
  say "启动 $name ..."
  nohup "$@" >"$log" 2>&1 &
  echo $! > "$pf"
  say "  pid $(cat "$pf")，日志 $log"
}

# --- 0. 工具检查 -------------------------------------------------------------
command -v uv     >/dev/null 2>&1 || die "未找到 uv —— 请先安装 https://docs.astral.sh/uv/"
command -v npm    >/dev/null 2>&1 || die "未找到 npm —— 请安装 Node.js 20+"
command -v node   >/dev/null 2>&1 || die "未找到 node —— 请安装 Node.js"

# --- Configuration + backend dependencies ----------------------------------
cd "$ROOT/backend"
if [ ! -f .env ]; then
  say "首次运行：使用本地 SQLite 演示配置（无需 Docker）"
  cp .env.demo.example .env
fi
[ -d .venv ] || { say "首次运行：安装后端依赖（uv sync）..."; uv sync; }
LOCAL_DEMO="$(uv run python -c 'from app.core.config import settings; print("true" if settings.local_demo else "false")')"
cd "$ROOT"

if [ "$LOCAL_DEMO" = "true" ]; then
  say "本地 SQLite 演示：不启动 Docker、Redis、Celery worker/beat"
  (cd "$ROOT/backend" && uv run python ../scripts/init_demo.py)
else
command -v docker >/dev/null 2>&1 || die "未找到 docker —— 请先安装 Docker Desktop 并启动它"
# --- 1. 基础设施（Postgres + Redis）------------------------------------------
say "启动 Docker 基础设施（PostgreSQL + Redis）..."
docker compose -f docker-compose.dev.yml up -d

say "等待 Postgres / Redis 健康（最多约 90 秒）..."
pg=; rd=
for _ in $(seq 1 45); do
  ps_out=$(docker compose -f docker-compose.dev.yml ps --format '{{.Service}} {{.Health}}' 2>/dev/null || true)
  pg=$(printf '%s\n' "$ps_out" | awk '$1=="postgres"{print $2}')
  rd=$(printf '%s\n' "$ps_out" | awk '$1=="redis"{print $2}')
  { [ "$pg" = "healthy" ] && [ "$rd" = "healthy" ]; } && break
  sleep 2
done
{ [ "$pg" = "healthy" ] && [ "$rd" = "healthy" ]; } \
  || die "基础设施未就绪（postgres=$pg redis=$rd）—— 请运行 docker compose -f docker-compose.dev.yml ps 排查"

# --- 2. 后端依赖 + 迁移 ------------------------------------------------------
cd "$ROOT/backend"
say "数据库迁移（alembic upgrade head）..."
uv run alembic upgrade head
fi

# --- 3. 后端 API -------------------------------------------------------------
cd "$ROOT/backend"
if port_ok http://localhost:8000/api/v1/health; then
  RUNNING_LOCAL_DEMO="$(curl -sf -m 3 http://localhost:8000/api/v1/auth/config | \
    uv run python -c 'import json,sys; print("true" if json.load(sys.stdin).get("local_demo") else "false")')"
  [ "$RUNNING_LOCAL_DEMO" = "$LOCAL_DEMO" ] || \
    die "后端仍在使用旧的数据库模式。请先停止本项目后端，再重新启动。"
  say "后端 API 已在运行（:8000），跳过"
else
  start_bg "后端 API（:8000）" "$RUN_DIR/backend.pid" "$LOG_DIR/backend.log" \
    uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
  say "等待后端就绪..."
  for _ in $(seq 1 30); do port_ok http://localhost:8000/api/v1/health && break; sleep 1; done
  port_ok http://localhost:8000/api/v1/health \
    || die "后端未能启动 —— 看日志 $LOG_DIR/backend.log"
fi

if [ "$LOCAL_DEMO" != "true" ]; then
# --- 4. Celery worker --------------------------------------------------------
# DATABASE_POOLCLASS=null: 每个 asyncio.run() 任务用独立连接，避免跨事件循环
# 复用连接导致 "Event loop is closed"（与测试同款做法）。export 让启动的进程
# 直接继承，pidfile 指向真正的 worker，stop 时 pidfile kill 即生效。
# 用 [c]elery 字符类破开模式，避免匹配到检测命令自身。
if proc_exists '[c]elery.*[c]elery_app.*worker'; then
  say "Celery worker 已在运行，跳过"
else
  export DATABASE_POOLCLASS=null
  start_bg "Celery worker（账单导入）" "$RUN_DIR/worker.pid" "$LOG_DIR/worker.log" \
    uv run celery -A app.workers.celery_app worker --loglevel=INFO --pool=solo
  sleep 4
  proc_exists '[c]elery.*[c]elery_app.*worker' || warn "worker 好像没起来？看日志 $LOG_DIR/worker.log"
fi

# --- 5. Celery beat ----------------------------------------------------------
if proc_exists '[c]elery.*[c]elery_app.*beat'; then
  say "Celery beat 已在运行，跳过"
else
  start_bg "Celery beat（周期付款）" "$RUN_DIR/beat.pid" "$LOG_DIR/beat.log" \
    uv run celery -A app.workers.celery_app beat --loglevel=INFO
  sleep 2
  proc_exists '[c]elery.*[c]elery_app.*beat' || warn "beat 好像没起来？看日志 $LOG_DIR/beat.log"
fi
fi

# --- 6. 前端 -----------------------------------------------------------------
if [ "$USE_FRONT" = "1" ]; then
  cd "$ROOT/frontend"
  [ -d node_modules ] || { say "首次运行：安装前端依赖（npm install）..."; npm install; }
  if port_ok http://localhost:5173/; then
    say "前端已在运行（:5173），跳过"
  else
    # Run Node directly: the Windows npm shell shim may lose its detached
    # child when Git Bash exits. Pin IPv4 and fail instead of changing ports.
    start_bg "前端（:5173）" "$RUN_DIR/frontend.pid" "$LOG_DIR/frontend.log" \
      node "$ROOT/frontend/node_modules/vite/bin/vite.js" --host 127.0.0.1 --strictPort
    for _ in $(seq 1 30); do port_ok http://localhost:5173/ && break; sleep 1; done
    port_ok http://localhost:5173/ || die "前端未启动 —— 看日志 $LOG_DIR/frontend.log"
  fi
fi

# --- 7. 演示数据（可选）------------------------------------------------------
if [ "$USE_DEMO" = "1" ]; then
  say "生成演示数据（--demo 将删除并重建演示用户的数据）..."
  # Load backend/.env even when the frontend branch changed our directory.
  (cd "$ROOT/backend" && uv run python ../scripts/demo_data.py --reset)
fi

# --- 完成 --------------------------------------------------------------------
echo
say "全部就绪 ✅"
printf '  后端 API : http://localhost:8000   接口文档: http://localhost:8000/docs\n'
[ "$USE_FRONT" = "1" ] && printf '  前端     : http://localhost:5173\n'
printf '  日志     : %s\n' "$LOG_DIR"
printf '  停止     : ./scripts/stop-dev.sh\n'
echo
if [ "$USE_DEMO" = "1" ]; then
  say "演示数据已生成；DEMO_MODE=true 时直接进入，否则登录 demoowner / demo123456"
else
  warn "模拟操作文件见 sample-data/workflow/；--demo 会删除并重建演示数据，请谨慎使用"
fi
echo
cmd //c start http://localhost:5173 >/dev/null 2>&1 || true
