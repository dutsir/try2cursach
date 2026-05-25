#!/usr/bin/env bash
# Полный сброс парсинга — убивает все процессы, чистит кэши, опционально
# делает warmup профиля и запускает worker.
#
# Usage:
#   ./scripts/reset_parser.sh                  # сброс + инструкции
#   ./scripts/reset_parser.sh --warmup         # сброс + warmup
#   ./scripts/reset_parser.sh --refresh        # обновить cookies без удаления профиля
#   ./scripts/reset_parser.sh --full           # сброс + warmup + старт worker
#   ./scripts/reset_parser.sh --check          # только проверки (без сброса)

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_DIR="$PROJECT_DIR/var/chrome_profiles/dns"

# ===== Цвета для красивого вывода =====
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
info() { echo -e "${BLUE}ℹ${NC} $1"; }
section() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

# ===== Проверки окружения =====
check_environment() {
    section "Проверка окружения"

    # Google Chrome
    if command -v google-chrome &>/dev/null; then
        ok "google-chrome: $(google-chrome --version)"
    else
        fail "google-chrome не установлен!"
        info "Установка: sudo apt install google-chrome-stable"
        return 1
    fi

    # Snap Chromium — конкурирующий браузер, мешает парсингу
    if command -v chromium-browser &>/dev/null || snap list 2>/dev/null | grep -q chromium; then
        warn "Найден snap-chromium — это КОНКУРИРУЮЩИЙ браузер!"
        warn "undetected_chromedriver может использовать его вместо Google Chrome,"
        warn "и парсер сломается (cookies/профиль не подходят)."
        echo ""
        info "Удалить: sudo snap remove chromium"
        echo ""
        read -r -p "Удалить snap-chromium СЕЙЧАС? [y/N] " ans
        if [[ "$ans" =~ ^[YyДд]$ ]]; then
            sudo snap remove chromium
            ok "snap-chromium удалён"
        else
            warn "Парсер может работать нестабильно пока snap-chromium на месте."
        fi
    else
        ok "snap-chromium не установлен (хорошо)"
    fi

    # Xvfb
    if command -v Xvfb &>/dev/null; then
        ok "Xvfb установлен"
    else
        fail "Xvfb не установлен!"
        info "Установка: sudo apt install xvfb"
        return 1
    fi

    # Display
    if [ -n "${DISPLAY:-}" ]; then
        ok "DISPLAY=$DISPLAY"
    else
        warn "DISPLAY не установлен (для warmup нужен :0 — реальный экран)"
    fi

    # Текущий IP
    local ip
    ip=$(curl -4 -s --max-time 5 ifconfig.me 2>/dev/null || echo "?")
    if [ "$ip" = "?" ]; then
        warn "Не удалось определить IP — проверь интернет"
    else
        ok "Твой IP (IPv4): $ip"
    fi

    return 0
}

# ===== Сброс =====
do_reset() {
    section "Сброс процессов"

    echo "🧹 Прибиваю celery..."
    pkill -9 -f celery 2>/dev/null || true

    echo "🧹 Прибиваю chrome/chromium..."
    pkill -9 -f chrome 2>/dev/null || true
    pkill -9 -f chromium 2>/dev/null || true
    pkill -9 -f chromedriver 2>/dev/null || true
    pkill -9 -f undetected 2>/dev/null || true

    echo "🧹 Прибиваю Xvfb..."
    pkill -9 Xvfb 2>/dev/null || true

    sleep 2

    section "Очистка кэшей"

    echo "🗑  X11 locks..."
    rm -f /tmp/.X99-lock
    rm -rf /tmp/.X11-unix/X99
    rm -f /tmp/com.google.Chrome.* 2>/dev/null || true

    echo "🗑  Chromedriver cache..."
    rm -rf ~/.local/share/undetected_chromedriver/
    rm -rf /tmp/undetected_chromedriver*

    echo "🗑  Chrome профиль..."
    rm -rf "$PROFILE_DIR"
    mkdir -p "$PROFILE_DIR"

    echo "🗑  Celery очередь..."
    cd "$PROJECT_DIR"
    # shellcheck disable=SC1091
    source venv/bin/activate
    celery -A config purge -f 2>/dev/null || true

    ok "Сброс выполнен"
}

# ===== Warmup =====
do_warmup() {
    section "Warmup Chrome профиля"
    echo ""
    echo "В открывшемся окне Chrome:"
    echo "  1. Зайди на главную DNS (если не откроется автоматически)"
    echo "  2. Пройди Qrator капчу если появится"
    echo "  3. Походи по сайту 1-2 минуты (открой пару категорий)"
    echo "  4. Закрой Chrome (Ctrl+Q или крестик)"
    echo ""
    echo "Скрипт ждёт пока ты закроешь Chrome..."
    echo ""

    export DISPLAY=:0
    google-chrome \
        --user-data-dir="$PROFILE_DIR" \
        --window-size=1920,1080 \
        --no-first-run \
        --no-default-browser-check \
        https://www.dns-shop.ru/

    ok "Warmup завершён, профиль накоплен в $PROFILE_DIR"
}

# ===== Запуск worker =====
do_start_worker() {
    section "Запуск Celery worker"

    # Xvfb
    if pgrep -f "Xvfb :99" >/dev/null; then
        info "Xvfb :99 уже работает"
    else
        echo "🖥  Стартую Xvfb :99..."
        Xvfb :99 -screen 0 1920x1080x24 -ac +extension RANDR &
        sleep 2
    fi

    info "Запускаю worker..."
    info "(Останови через Ctrl+C — НЕ Ctrl+Z)"
    echo ""
    exec "$PROJECT_DIR/scripts/run_celery_worker.sh"
}

# ===== Main =====
cmd="${1:-help}"

case "$cmd" in
    --check)
        check_environment
        ;;
    --warmup)
        check_environment || exit 1
        do_reset
        do_warmup
        echo ""
        info "Готово. Дальше:"
        info "  Xvfb :99 -screen 0 1920x1080x24 -ac +extension RANDR &"
        info "  ./scripts/run_celery_worker.sh"
        ;;
    --refresh)
        # Обновить Qrator cookies БЕЗ удаления профиля (история сохранится).
        # Полезно когда профиль ещё хороший, но Qrator выкинул сессию.
        check_environment || exit 1
        section "Обновление Qrator cookies (профиль сохраняется)"

        echo "🧹 Прибиваю активные Chrome процессы..."
        pkill -9 -f chrome 2>/dev/null || true
        pkill -9 -f chromedriver 2>/dev/null || true
        pkill -9 -f undetected 2>/dev/null || true
        sleep 1

        do_warmup
        ;;
    --full)
        check_environment || exit 1
        do_reset
        do_warmup
        do_start_worker
        ;;
    "")
        check_environment || exit 1
        do_reset
        echo ""
        info "Следующие шаги:"
        info "1. Warmup профиля:"
        info "   $0 --warmup"
        info ""
        info "2. Или всё сразу (сброс + warmup + worker):"
        info "   $0 --full"
        ;;
    help|--help|-h)
        cat <<EOF
Использование: $0 [команда]

Команды:
  (без аргументов)  Сброс процессов и кэшей. После — нужен warmup.
  --warmup          Сброс + warmup профиля (открывает Chrome для прохождения Qrator).
  --full            Сброс + warmup + автоматический запуск worker.
  --check           Только проверки окружения, ничего не делает.

Примеры:
  $0 --check           # узнать в каком я состоянии
  $0 --warmup          # сделать сброс и прогреть профиль
  $0 --full            # одной командой всё подготовить и запустить

EOF
        ;;
    *)
        fail "Неизвестная команда: $cmd"
        echo "Используй: $0 --help"
        exit 1
        ;;
esac
