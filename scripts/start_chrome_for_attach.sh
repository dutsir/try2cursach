#!/usr/bin/env bash
# Запускает Chrome в фоне в Xvfb с remote-debugging-port=9222.
# Парсер потом attach'ится к нему через CDP.
#
# Идея: один раз запускаешь Chrome (он работает в Xvfb, не виден),
# парсер целый день ходит через этот же Chrome.
# Qrator видит "обычный пользовательский Chrome", не Selenium.
#
# Usage:
#   ./scripts/start_chrome_for_attach.sh         # запуск
#   ./scripts/start_chrome_for_attach.sh stop    # остановка

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_DIR="$PROJECT_DIR/var/chrome_profiles/dns"
PID_FILE="/tmp/chrome_for_attach.pid"
PORT=9222

cmd="${1:-start}"

case "$cmd" in
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            echo "Останавливаю Chrome PID=$PID..."
            kill "$PID" 2>/dev/null || true
            rm -f "$PID_FILE"
        fi
        pkill -f "remote-debugging-port=$PORT" 2>/dev/null || true
        echo "Chrome остановлен."
        exit 0
        ;;
    start) ;;
    *)
        echo "Usage: $0 [start|stop]"
        exit 1
        ;;
esac

# Проверим что не запущен уже
if pgrep -f "remote-debugging-port=$PORT" >/dev/null; then
    echo "⚠ Chrome уже работает на порту $PORT."
    echo "Останови: $0 stop"
    exit 1
fi

mkdir -p "$PROFILE_DIR"

# Xvfb должен работать
if ! pgrep -f "Xvfb :99" >/dev/null; then
    echo "🖥  Стартую Xvfb :99..."
    Xvfb :99 -screen 0 1920x1080x24 -ac +extension RANDR &
    sleep 1
fi

export DISPLAY=:99

echo "🚀 Стартую Chrome в Xvfb (порт CDP: $PORT)..."

google-chrome \
    --remote-debugging-port=$PORT \
    --user-data-dir="$PROFILE_DIR" \
    --window-size=1920,1080 \
    --no-first-run \
    --no-default-browser-check \
    --disable-blink-features=AutomationControlled \
    --disable-features=IsolateOrigins,site-per-process \
    --disable-dev-shm-usage \
    https://www.dns-shop.ru/ &

CHROME_PID=$!
echo $CHROME_PID > "$PID_FILE"

echo "✓ Chrome запущен (PID: $CHROME_PID)"
echo ""
echo "Подождём 10 сек чтобы Chrome пол­ностью стартовал..."
sleep 10

# Проверим что CDP отвечает
if curl -s "http://127.0.0.1:$PORT/json/version" >/dev/null; then
    echo "✓ CDP доступен на 127.0.0.1:$PORT"
    echo ""
    curl -s "http://127.0.0.1:$PORT/json/version" | python -m json.tool 2>/dev/null | head -10 || true
    echo ""
    echo "Парсер теперь может attach'иться к этому Chrome."
    echo ""
    echo "Чтобы остановить: $0 stop"
else
    echo "❌ CDP не отвечает на порту $PORT"
    exit 1
fi
