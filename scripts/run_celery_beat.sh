#!/usr/bin/env bash
# Запуск Celery beat (планировщик периодических задач).
# Beat не запускает парсинг сам — он отправляет задачи в очередь,
# а worker их выполняет. Поэтому Xvfb здесь не нужен.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$PROJECT_DIR/venv/bin/activate"

echo "⏰ Стартую Celery beat..."
exec celery -A config beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
