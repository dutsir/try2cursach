#!/usr/bin/env bash
# Деплой на VPS.
# Режимы:
#   DEPLOY_MODE=site      — только web + frontend (по умолчанию)
#   DEPLOY_MODE=site+wb   — web + frontend + WB-парсер (лёгкий celery + beat)
#
# Использование:
#   PROJECT_DIR=/opt/price_monitor bash scripts/deploy.sh
#   DEPLOY_MODE=site+wb PROJECT_DIR=/opt/price_monitor bash scripts/deploy.sh
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/price_monitor}"
DEPLOY_MODE="${DEPLOY_MODE:-site}"
cd "$PROJECT_DIR"

# VPS: web-light + HTTPS nginx (см. docker-compose.vps.yml).
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.vps.yml)

# Создаём внешний Docker volume для БД, если его ещё нет.
# (docker compose down -v НЕ удаляет external-volumes — данные в безопасности)
if ! docker volume inspect pm_postgres_data &>/dev/null; then
    echo "[$(date)] Создаём volume pm_postgres_data…"
    docker volume create pm_postgres_data
fi

echo "[$(date)] Pulling latest code…"
git pull --ff-only

if [[ "$DEPLOY_MODE" == "site+wb" ]]; then
    echo "[$(date)] Rebuilding containers (web + frontend + celery-light)…"
    "${COMPOSE[@]}" build web frontend celery-worker-vps celery-beat
else
    echo "[$(date)] Rebuilding containers (web + frontend only)…"
    "${COMPOSE[@]}" build web frontend
fi

echo "[$(date)] Restarting services…"
if [[ "$DEPLOY_MODE" == "site+wb" ]]; then
    # up -d поднимает сервисы без profile (postgres, redis, rabbitmq, web, frontend)
    # + profile vps-celery (celery-worker-vps + celery-beat).
    "${COMPOSE[@]}" --profile vps-celery up -d
else
    # Только базовые сервисы без Celery.
    "${COMPOSE[@]}" up -d
fi

echo "[$(date)] Waiting for web to be ready…"
for i in $(seq 1 15); do
    if "${COMPOSE[@]}" exec -T web python manage.py check --deploy --fail-level ERROR 2>/dev/null; then
        break
    fi
    echo "  [${i}/15] waiting…"
    sleep 3
done

echo "[$(date)] Deploy complete."
"${COMPOSE[@]}" ps
