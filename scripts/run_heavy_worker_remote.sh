#!/usr/bin/env bash
# Запуск ЛОКАЛЬНОГО тяжёлого воркера (DNS/Citilink/Ozon/MVideo на Chrome+Xvfb),
# который пишет в БД на VPS ЧЕРЕЗ WireGuard.
#
# Зачем отдельная обёртка, а не правка .env:
#   dev .env указывает на localhost (локальный docker-стек). Этот скрипт берёт
#   ОТДЕЛЬНЫЙ .env.remote (креды VPS + хосты 10.10.0.x) и экспортирует его ДО
#   запуска celery. settings.py делает load_dotenv(override=False) — значит уже
#   экспортированные переменные побеждают .env. Так dev-окружение не ломается.
#
# Предусловия:
#   1) WireGuard поднят (scripts/setup_wireguard_local.sh, ping 10.10.0.1 проходит)
#   2) .env.home-dns-worker заполнен (скопировать из .env.home-dns-worker.example)
#   3) HF-кэш модели эмбеддингов есть локально (дедуп с эмбеддингами работает)
#
# Чем удобнее, чем `cp .env.home-dns-worker.example .env` из runbook: НЕ затирает
# твой dev .env. Берёт отдельный файл и экспортирует его перед celery — а
# settings.py делает load_dotenv(override=False), так что эти значения побеждают.
#
# Использование:
#   bash scripts/run_heavy_worker_remote.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

ENV_REMOTE="${ENV_REMOTE:-$PROJECT_DIR/.env.home-dns-worker}"
if [[ ! -f "$ENV_REMOTE" ]]; then
    echo "Нет $ENV_REMOTE."
    echo "Скопируй и заполни: cp .env.home-dns-worker.example .env.home-dns-worker"
    exit 1
fi

# Проверяем что туннель жив (БД на VPS доступна только через него).
VPS_WG_ADDR="${VPS_WG_ADDR:-10.10.0.1}"
if ! ping -c1 -W2 "$VPS_WG_ADDR" >/dev/null 2>&1; then
    echo "VPS ($VPS_WG_ADDR) недоступен по WireGuard."
    echo "Подними туннель: sudo wg-quick up wg0  (и проверь ping $VPS_WG_ADDR)"
    exit 1
fi

# Экспортируем переменные VPS — они победят dev .env (load_dotenv override=False).
set -a
# shellcheck disable=SC1090
source "$ENV_REMOTE"
set +a

# Локальный воркер обслуживает ТОЛЬКО тяжёлую очередь.
# Лёгкие задачи (WB) и служебные (подписки) обрабатывает celery-worker-vps на VPS.
export CELERY_QUEUES="parsing_heavy"
export CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-1}"

echo "[remote-heavy] БД/брокер: ${DB_HOST}  очередь: parsing_heavy"
exec "$PROJECT_DIR/scripts/run_celery_worker.sh"
