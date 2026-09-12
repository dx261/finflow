#!/usr/bin/env bash
# FinFlow 一键停止（开发模式）
# 停止 start-dev.sh 拉起的后端 / worker / 前端（Docker 基础设施保留）。
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="$ROOT/.run"

say() { printf '\033[1;34m[finflow]\033[0m %s\n' "$*"; }

kill_by_regex() { # $1 命令行正则  $2 名称
  local pids
  pids=$(powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '$1' } | ForEach-Object { \$_.ProcessId }" 2>/dev/null)
  for pid in $pids; do
    case "$pid" in
      *[!0-9]*|'') ;;
      *) taskkill //PID "$pid" //F >/dev/null 2>&1 && say "已终止 $2 (pid $pid)" ;;
    esac
  done
}

# 1) 先按 pidfile 杀主进程（uv run 已 exec 进真正的服务进程）
for entry in "backend.pid:uvicorn:后端 API" "worker.pid:celery:worker" "frontend.pid:vite:前端"; do
  pf="$RUN_DIR/${entry%%:*}"; rest="${entry#*:}"; pat="${rest%%:*}"; name="${rest#*:}"
  if [ -f "$pf" ]; then
    pid=$(cat "$pf")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && say "已停止 $name (pid $pid)"
    fi
    rm -f "$pf"
  fi
done

# 2) 兜底：按命令行特征清理残留（Windows 上服务进程是 python.exe/node.exe，防子进程没死透）
# 用字符类 [a]pp/[c]elery/[v]ite 破开模式，避免匹配到本脚本自己的命令行
kill_by_regex '[a]pp\.main:app'  '后端 API 残留'
kill_by_regex '[c]elery_app'     'worker 残留'
kill_by_regex '[v]ite'           '前端残留'

say "完成。Postgres/Redis 仍在 Docker 里运行；如需彻底停掉: docker compose -f docker-compose.dev.yml down"
