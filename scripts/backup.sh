#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/price_monitor/backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"
CONTAINER="${DB_CONTAINER:-pm_postgres}"
DB_NAME="${DB_NAME:-price_monitor}"
DB_USER="${DB_USER:-pm_user}"
PROJECT_DIR="${PROJECT_DIR:-/opt/price_monitor}"
# Профили Chrome (qrator_jsid и пр.) — важны для DNS: их «прогрев» небыстрый,
# и при потере профиля DNS снова отдаёт challenge/403.
CHROME_PROFILES_DIR="${CHROME_PROFILES_DIR:-$PROJECT_DIR/var/chrome_profiles}"
DATE=$(date +%F_%H%M)

mkdir -p "$BACKUP_DIR"

docker exec "$CONTAINER" pg_dump -Fc -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/${DB_NAME}_${DATE}.dump"
echo "[$(date)] DB backup: ${DB_NAME}_${DATE}.dump"

if [ -d "$CHROME_PROFILES_DIR" ]; then
    tar -czf "$BACKUP_DIR/chrome_profiles_${DATE}.tar.gz" -C "$(dirname "$CHROME_PROFILES_DIR")" "$(basename "$CHROME_PROFILES_DIR")"
    echo "[$(date)] Chrome profiles backup: chrome_profiles_${DATE}.tar.gz"
else
    echo "[$(date)] Chrome profiles dir not found ($CHROME_PROFILES_DIR), skipped"
fi

find "$BACKUP_DIR" -name "*.dump" -mtime "+$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name "chrome_profiles_*.tar.gz" -mtime "+$KEEP_DAYS" -delete

echo "[$(date)] Backup done (kept last $KEEP_DAYS days)"
