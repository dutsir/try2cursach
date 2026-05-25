#!/usr/bin/env bash
set -euo pipefail

DUMP_FILE="$1"
CONTAINER="${DB_CONTAINER:-pm_postgres}"
DB_NAME="${DB_NAME:-price_monitor}"
DB_USER="${DB_USER:-pm_user}"

if [ -z "${DUMP_FILE:-}" ]; then
    echo "Usage: $0 <path-to-dump-file>"
    exit 1
fi

docker exec -i "$CONTAINER" pg_restore --clean --if-exists -U "$DB_USER" -d "$DB_NAME" < "$DUMP_FILE"
echo "[$(date)] Restored: $DUMP_FILE → $DB_NAME"
