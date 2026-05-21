#!/usr/bin/env bash
# Запуск Celery worker с виртуальным дисплеем Xvfb для парсеров.
#
# Логика:
# - Стартуем Xvfb на дисплее :99 (виртуальный экран 1920x1080)
# - Экспортируем DISPLAY=:99 для всех дочерних процессов (Chrome)
# - Запускаем Celery worker с prefork pool и ограниченной concurrency
# - При завершении (Ctrl+C) корректно останавливаем Xvfb
#
# Использование:
#   ./scripts/run_celery_worker.sh                  # дефолт: concurrency=2
#   CELERY_CONCURRENCY=4 ./scripts/run_celery_worker.sh
#
# Альтернатива через VS Code:
#   Tasks → "Celery: worker with Xvfb"

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Активируем venv
# shellcheck disable=SC1091
source "$PROJECT_DIR/venv/bin/activate"

# Параметры
DISPLAY_NUM="${DISPLAY_NUM:-99}"
XVFB_RESOLUTION="${XVFB_RESOLUTION:-1920x1080x24}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-2}"
CELERY_LOGLEVEL="${CELERY_LOGLEVEL:-info}"

# Проверяем что Xvfb установлен
if ! command -v Xvfb &>/dev/null; then
    echo "❌ Xvfb не установлен. Установи: sudo apt install -y xvfb"
    exit 1
fi

# Чистим старый Xvfb на нашем дисплее если есть
if pgrep -f "Xvfb :${DISPLAY_NUM}" >/dev/null; then
    echo "⚠ Найден работающий Xvfb на :${DISPLAY_NUM}, останавливаю..."
    pkill -f "Xvfb :${DISPLAY_NUM}" || true
    sleep 1
fi

# Стартуем Xvfb в фоне
echo "🖥  Стартую Xvfb :${DISPLAY_NUM} ($XVFB_RESOLUTION)..."
Xvfb ":${DISPLAY_NUM}" -screen 0 "$XVFB_RESOLUTION" -ac +extension RANDR &
XVFB_PID=$!

# Гарантия что Xvfb остановится при выходе
cleanup() {
    echo ""
    echo "🛑 Останавливаю Xvfb (PID $XVFB_PID)..."
    kill "$XVFB_PID" 2>/dev/null || true
    wait "$XVFB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Ждём пока Xvfb поднимется
sleep 1

export DISPLAY=":${DISPLAY_NUM}"
echo "✅ DISPLAY=$DISPLAY"

# Запускаем Celery worker
# --pool=prefork: параллельные процессы (на Linux работает в отличие от Windows)
# --concurrency: количество параллельных worker-процессов
#   Для Chrome-парсеров не больше 2-4, иначе RAM кончится (каждый Chrome ~500MB)
# -Q default: можно потом разделить очереди (parsing, light)
echo "🚀 Стартую Celery worker (concurrency=$CELERY_CONCURRENCY)..."
exec celery -A config worker \
    --loglevel="$CELERY_LOGLEVEL" \
    --pool=prefork \
    --concurrency="$CELERY_CONCURRENCY" \
    --max-tasks-per-child=10 \
    --hostname="worker@%h"
