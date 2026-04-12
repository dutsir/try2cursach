#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/price_monitor}"
cd "$PROJECT_DIR"

echo "[$(date)] Pulling latest code…"
git pull --ff-only

echo "[$(date)] Rebuilding containers…"
docker compose build

echo "[$(date)] Applying migrations…"
docker compose run --rm web python manage.py migrate

echo "[$(date)] Seeding categories…"
docker compose run --rm web python manage.py seed_categories --update

echo "[$(date)] Restarting services…"
docker compose up -d

echo "[$(date)] Deploy complete."
docker compose ps
