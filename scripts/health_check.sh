#!/usr/bin/env bash
# Health check для всего dev стека: Docker сервисы + Django + БД
# Запуск: ./scripts/health_check.sh

set -u

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

ok() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
info() { echo -e "${BLUE}ℹ${NC} $1"; }
section() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

ERRORS=0

# --- 1. Docker ---
section "1. Docker"
if command -v docker &>/dev/null; then
    ok "docker установлен ($(docker --version | awk '{print $3}' | tr -d ','))"
else
    fail "docker не установлен"
    ((ERRORS++))
fi

if docker compose version &>/dev/null; then
    ok "docker compose работает"
else
    fail "docker compose не работает"
    ((ERRORS++))
fi

# --- 2. Контейнеры ---
section "2. Контейнеры"
for svc in pm_postgres pm_rabbitmq pm_redis; do
    status=$(docker inspect -f '{{.State.Status}}' "$svc" 2>/dev/null || echo "missing")
    if [ "$status" = "running" ]; then
        ok "$svc: running"
    elif [ "$status" = "missing" ]; then
        warn "$svc: не создан (запусти 'docker compose up -d')"
    else
        fail "$svc: $status"
        ((ERRORS++))
    fi
done

# --- 3. PostgreSQL ---
section "3. PostgreSQL"
if docker exec pm_postgres pg_isready -U postgres &>/dev/null; then
    ok "postgres готов принимать подключения"

    PG_VER=$(docker exec pm_postgres psql -U postgres -t -c "SHOW server_version;" 2>/dev/null | xargs)
    ok "PostgreSQL версия: $PG_VER"

    if docker exec pm_postgres psql -U postgres -lqt 2>/dev/null | grep -q curcash; then
        ok "БД 'curcash' существует"

        VECTOR=$(docker exec pm_postgres psql -U postgres -d curcash -t -c "SELECT extversion FROM pg_extension WHERE extname='vector';" 2>/dev/null | xargs)
        [ -n "$VECTOR" ] && ok "Расширение vector: $VECTOR" || fail "vector не установлен"

        TS=$(docker exec pm_postgres psql -U postgres -d curcash -t -c "SELECT extversion FROM pg_extension WHERE extname='timescaledb';" 2>/dev/null | xargs)
        [ -n "$TS" ] && ok "Расширение timescaledb: $TS" || warn "timescaledb не установлен (OK для dev)"

        PROD_COUNT=$(docker exec pm_postgres psql -U postgres -d curcash -t -c "SELECT COUNT(*) FROM products_product;" 2>/dev/null | xargs)
        if [ -n "$PROD_COUNT" ]; then
            ok "Товаров в БД: $PROD_COUNT"
        else
            warn "Таблица products_product отсутствует (нужны миграции)"
        fi
    else
        fail "БД 'curcash' не существует"
        ((ERRORS++))
    fi
else
    fail "postgres не готов"
    ((ERRORS++))
fi

# --- 4. Redis ---
section "4. Redis"
if docker exec pm_redis redis-cli ping 2>/dev/null | grep -q PONG; then
    ok "redis отвечает PONG"
else
    fail "redis не отвечает"
    ((ERRORS++))
fi

# --- 5. RabbitMQ ---
section "5. RabbitMQ"
if docker exec pm_rabbitmq rabbitmq-diagnostics -q ping 2>/dev/null | grep -q "Ping succeeded"; then
    ok "rabbitmq отвечает"
    info "Management UI: http://localhost:15672 (guest/guest)"
else
    fail "rabbitmq не отвечает"
    ((ERRORS++))
fi

# --- 6. Python venv ---
section "6. Python venv"
if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    PY_VER=$("$PROJECT_DIR/venv/bin/python" --version 2>&1)
    ok "venv: $PY_VER"

    if "$PROJECT_DIR/venv/bin/python" -c "import django" 2>/dev/null; then
        DJ_VER=$("$PROJECT_DIR/venv/bin/python" -c "import django; print(django.get_version())")
        ok "Django: $DJ_VER"
    else
        fail "Django не установлен в venv"
        ((ERRORS++))
    fi
else
    fail "venv не найден"
    ((ERRORS++))
fi

# --- 7. Django check ---
section "7. Django"
if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    DJ_CHECK=$("$PROJECT_DIR/venv/bin/python" manage.py check 2>&1)
    if echo "$DJ_CHECK" | grep -q "no issues"; then
        ok "manage.py check: no issues"
    else
        fail "manage.py check failed:"
        echo "$DJ_CHECK" | head -5
        ((ERRORS++))
    fi

    UNAPPLIED=$("$PROJECT_DIR/venv/bin/python" manage.py showmigrations --plan 2>/dev/null | grep -c "^\[ \]")
    if [ "$UNAPPLIED" -eq 0 ] 2>/dev/null; then
        ok "Все миграции применены"
    else
        warn "Не применено миграций: $UNAPPLIED (запусти 'python manage.py migrate')"
    fi
fi

# --- 8. Chrome + Xvfb (для парсинга) ---
section "8. Chrome + Xvfb"
if command -v google-chrome &>/dev/null || command -v chromium-browser &>/dev/null || command -v chromium &>/dev/null; then
    BROWSER=$(command -v google-chrome chromium-browser chromium 2>/dev/null | head -1)
    BROWSER_VER=$("$BROWSER" --version 2>/dev/null | awk '{print $NF}')
    ok "Браузер: $BROWSER ($BROWSER_VER)"
else
    warn "Chrome/Chromium не установлен (нужен для Selenium-парсеров)"
    info "Установка: sudo apt install chromium-browser"
    info "Или Google Chrome (рекомендую): https://www.google.com/chrome/"
fi

if command -v Xvfb &>/dev/null; then
    ok "Xvfb установлен"
    if pgrep -f "Xvfb :99" >/dev/null; then
        ok "Xvfb работает на :99"
    else
        info "Xvfb не запущен (запустится автоматически через run_celery_worker.sh)"
    fi
else
    warn "Xvfb не установлен (нужен для невидимого парсинга)"
    info "Установка: sudo apt install xvfb"
fi

# --- Итог ---
echo ""
section "ИТОГ"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 Все системы работают штатно!${NC}"
    echo ""
    info "Запусти Django: python manage.py runserver"
    info "Запусти Celery worker: celery -A config worker -l info"
    info "Запусти Celery beat: celery -A config beat -l info"
else
    echo -e "${RED}Найдено ошибок: $ERRORS${NC}"
    exit 1
fi
