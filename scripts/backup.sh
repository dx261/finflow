#!/usr/bin/env bash
# FinFlow backup script (TASK-058).
#
# Produces a single timestamped archive containing:
#   1. PostgreSQL dump          (docker compose exec postgres pg_dump)
#   2. Redis RDB snapshot       (best-effort; broker data is ephemeral)
#   3. Uploaded statement files (uploads_data volume, or host ./backend/data)
#
# Works against both the dev stack and the production stack: pick the
# compose file with COMPOSE_FILE (default: docker-compose.dev.yml).
#
# Usage:
#   ./scripts/backup.sh                      # dev stack -> ./backups/
#   COMPOSE_FILE=docker-compose.yml ./scripts/backup.sh   # production stack
#   BACKUP_DIR=/mnt/backups ./scripts/backup.sh
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK_DIR="$(mktemp -d)"
ARCHIVE="$BACKUP_DIR/finflow-backup-$STAMP.tar.gz"

mkdir -p "$BACKUP_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "==> Compose file: $COMPOSE_FILE"
echo "==> Backup archive: $ARCHIVE"

# --- 1. PostgreSQL -------------------------------------------------------
echo "==> Dumping PostgreSQL..."
if docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-finflow}" -d "${POSTGRES_DB:-finflow}" \
    > "$WORK_DIR/postgres.sql"; then
  echo "    postgres.sql $(wc -c < "$WORK_DIR/postgres.sql") bytes"
else
  echo "    WARNING: PostgreSQL dump failed (is the stack running?)"
  rm -f "$WORK_DIR/postgres.sql"
fi

# --- 2. Redis (best effort) ----------------------------------------------
echo "==> Snapshotting Redis (best effort)..."
if docker compose -f "$COMPOSE_FILE" exec -T redis sh -c \
    "redis-cli SAVE >/dev/null && cat /data/dump.rdb" > "$WORK_DIR/redis.rdb" 2>/dev/null; then
  echo "    redis.rdb $(wc -c < "$WORK_DIR/redis.rdb") bytes"
else
  echo "    WARNING: Redis snapshot skipped (broker data is ephemeral)"
  rm -f "$WORK_DIR/redis.rdb"
fi

# --- 3. Uploaded statement files ----------------------------------------
echo "==> Backing up uploads..."
PROJECT_NAME="$(docker compose -f "$COMPOSE_FILE" config | head -1 | awk '{print $2}')"
VOLUME_NAME="${PROJECT_NAME}_uploads_data"
if docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
  docker run --rm -v "$VOLUME_NAME:/data:ro" -v "$WORK_DIR:/backup" alpine \
    sh -c "tar czf /backup/uploads.tar.gz -C /data ." 2>/dev/null && \
    echo "    uploads.tar.gz $(wc -c < "$WORK_DIR/uploads.tar.gz") bytes" || \
    echo "    WARNING: uploads volume backup failed"
elif [ -d ./backend/data/uploads ]; then
  tar czf "$WORK_DIR/uploads.tar.gz" -C ./backend/data/uploads . 2>/dev/null && \
    echo "    uploads.tar.gz (host dir) $(wc -c < "$WORK_DIR/uploads.tar.gz") bytes"
else
  echo "    no uploads found to back up"
fi

# --- Archive --------------------------------------------------------------
if [ -z "$(ls -A "$WORK_DIR")" ]; then
  echo "!! Nothing was backed up — aborting."
  exit 1
fi

tar czf "$ARCHIVE" -C "$WORK_DIR" .
rm -rf "$WORK_DIR"
trap - EXIT

echo "==> Done: $ARCHIVE"
