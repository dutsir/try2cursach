#!/usr/bin/env bash
# Entrypoint тяжёлого Celery-воркера (DNS/Citilink/Ozon): поднимает Xvfb НАДЁЖНО,
# затем запускает переданную команду (celery ...). Зачем отдельный скрипт, а не
# inline `sh -c "Xvfb & exec celery"` в compose:
#   1. Старый вариант писал вывод Xvfb в /dev/null и не проверял, что X-сервер
#      реально поднялся. При рестарте контейнера оставался stale /tmp/.X99-lock,
#      Xvfb молча падал из-за гонки, а каждый парсинг падал с "chrome not reachable".
#   2. Folded-скаляр YAML (`>`) с многострочным sh -c легко ломался (переводы строк
#      превращались в разделители команд). Здесь команда передаётся как "$@" одной
#      строкой — без этой ловушки.
set -euo pipefail

DISPLAY_ADDR="${DISPLAY:-:99}"
DISPLAY_NUM="${DISPLAY_ADDR#:}"
X_SOCKET="/tmp/.X11-unix/X${DISPLAY_NUM}"
X_LOCK="/tmp/.X${DISPLAY_NUM}-lock"

# Снимаем stale lock/сокет от прошлого запуска контейнера, иначе новый Xvfb
# не стартует ("Server is already active for display").
rm -f "$X_LOCK" "$X_SOCKET" 2>/dev/null || true

echo "[entrypoint] Запускаю Xvfb на $DISPLAY_ADDR" >&2
Xvfb "$DISPLAY_ADDR" -screen 0 1920x1080x24 -nolisten tcp &
XVFB_PID=$!

# Ждём, пока X-сервер реально начнёт принимать соединения. Признак готовности —
# появление unix-сокета (его мы только что удалили, так что повторное появление
# = Xvfb готов). Параллельно следим, что процесс Xvfb жив.
for _ in $(seq 1 40); do
  if [ -S "$X_SOCKET" ]; then
    echo "[entrypoint] Xvfb готов (сокет $X_SOCKET)" >&2
    break
  fi
  if ! kill -0 "$XVFB_PID" 2>/dev/null; then
    echo "[entrypoint] ОШИБКА: Xvfb упал при старте" >&2
    exit 1
  fi
  sleep 0.5
done

if [ ! -S "$X_SOCKET" ]; then
  echo "[entrypoint] ОШИБКА: Xvfb не поднялся за 20с" >&2
  exit 1
fi

exec "$@"
