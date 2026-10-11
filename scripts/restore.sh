#!/usr/bin/env bash
# FinFlow restore script (TASK-058).
#
# Restores the contents of a backup archive produced by scripts/backup.sh:
#   1. postgres.sql     -> piped back into PostgreSQL (drops schema first)
#   2. uploads.tar.gz   -> extracted into the uploads_data volume
#   3. redis.rdb        -> NOT restored automatically (broker data is
#                          ephemeral and would be re-derived)
#
# DANGER: restoring overwrites the current database contents.
#
# Usage:
#   ./scripts/restore.sh backups/finflow-backup-20260912-120000.tar.gz
#   COMPOSE_FILE=docker-compose.yml ./scripts/restore.sh backups/...tar.gz
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"

if [ $# -ne 1 ]; then
  echo "Usage: $0 <backup-archive.tar.gz>" >&2
  exit 1
fi
ARCHIVE="$1"

if [ ! -f "$ARCHIVE" ]; then
  echo "Backup archive not found: $ARCHIVE" >&2
  exit 1
fi

echo "==> Restoring $ARCHIVE (compose file: $COMPOSE_FILE)"

read -r -p "This overwrites current data. Continue? [y/N] " CONFIRM
if [ "${CONFIRM:-n}" != "y" ] && [ "${CONFIRM:-n}" != "Y" ]; then
  echo "Aborted."
  exit 0
fi

WORK_DIR="$(mktemp -d)"
RUNNING_WRITERS=()
cleanup() {
  rm -rf "$WORK_DIR"
  if [ ${#RUNNING_WRITERS[@]} -gt 0 ]; then
    docker compose -f "$COMPOSE_FILE" start "${RUNNING_WRITERS[@]}" >/dev/null
  fi
}
trap cleanup EXIT
if tar tzf "$ARCHIVE" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
  echo "Backup contains unsafe paths; restore aborted." >&2
  exit 1
fi
tar xzf "$ARCHIVE" -C "$WORK_DIR"

if [ ! -f "$WORK_DIR/manifest.sha256" ] || [ ! -f "$WORK_DIR/postgres.sql" ]; then
  echo "Backup manifest or PostgreSQL dump is missing; restore aborted." >&2
  exit 1
fi
(cd "$WORK_DIR" && sha256sum -c manifest.sha256)

# Stop every writer before replacing the schema/files.  The EXIT trap starts
# only services that were running before the restore, including on failure.
for service in api worker beat; do
  if docker compose -f "$COMPOSE_FILE" ps --status running --services | grep -qx "$service"; then
    RUNNING_WRITERS+=("$service")
  fi
done
if [ ${#RUNNING_WRITERS[@]} -gt 0 ]; then
  docker compose -f "$COMPOSE_FILE" stop "${RUNNING_WRITERS[@]}"
fi

# --- 1. PostgreSQL -------------------------------------------------------
if [ -f "$WORK_DIR/postgres.sql" ]; then
  echo "==> Restoring PostgreSQL..."
  # Drop public schema so the restore is a clean slate, then recreate it.
  docker compose -f "$COMPOSE_FILE" exec -T postgres \
    sh -c "psql -U ${POSTGRES_USER:-finflow} -d ${POSTGRES_DB:-finflow} \
           -c 'DROP SCHEMA public CASCADE' -c 'CREATE SCHEMA public'"
  docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U "${POSTGRES_USER:-finflow}" -d "${POSTGRES_DB:-finflow}" < "$WORK_DIR/postgres.sql"
  echo "    PostgreSQL restored."
else
  echo "    No postgres.sql in archive — skipped."
fi

# --- 2. Uploads ----------------------------------------------------------
if [ -f "$WORK_DIR/uploads.tar.gz" ]; then
  echo "==> Restoring uploads..."
  PROJECT_NAME="$(docker compose -f "$COMPOSE_FILE" config | head -1 | awk '{print $2}')"
  VOLUME_NAME="${PROJECT_NAME}_uploads_data"
  if docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
    docker run --rm -v "$VOLUME_NAME:/data" -v "$WORK_DIR:/backup" alpine \
      sh -c "rm -rf /data/* && tar xzf /backup/uploads.tar.gz -C /data" && \
      echo "    uploads restored."
  else
    echo "    WARNING: uploads_data volume not found — skipped."
  fi
else
  echo "    No uploads.tar.gz in archive — skipped."
fi

# --- 3. Redis ------------------------------------------------------------
if [ -f "$WORK_DIR/redis.rdb" ]; then
  echo "    Redis snapshot present but intentionally not restored (ephemeral broker data)."
fi

echo "==> Restore complete. Previously running writer services are being restarted."
