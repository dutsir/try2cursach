#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/price_monitor/backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"
CONTAINER="${DB_CONTAINER:-pm_postgres}"
DB_NAME="${DB_NAME:-price_monitor}"
DB_USER="${DB_USER:-pm_user}"
DATE=$(date +%F_%H%M)

mkdir -p "$BACKUP_DIR"

docker exec "$CONTAINER" pg_dump -Fc -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/${DB_NAME}_${DATE}.dump"

find "$BACKUP_DIR" -name "*.dump" -mtime "+$KEEP_DAYS" -delete

echo "[$(date)] Backup: ${DB_NAME}_${DATE}.dump (kept last $KEEP_DAYS days)"
