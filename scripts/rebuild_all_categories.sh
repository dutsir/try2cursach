#!/usr/bin/env bash
# Применяет rebuild_master_products для всех категорий по очереди.
# Показывает чек-лист прогресса в реальном времени.
#
# Использование:
#   ./scripts/rebuild_all_categories.sh                    # все категории
#   ./scripts/rebuild_all_categories.sh --skip videokarty,monitory  # пропустить
#   ./scripts/rebuild_all_categories.sh --threshold 0.75   # снизить порог
#   ./scripts/rebuild_all_categories.sh --dry-run          # только посмотреть
#
# Лог: var/rebuild_all_$(date).log
# Чек-лист: var/rebuild_checklist_$(date).log

set -u  # exit on undefined variable, но НЕ на ошибку команды

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
source venv/bin/activate

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
GRAY='\033[0;90m'
NC='\033[0m'

# Параметры
MODE="--apply"
THRESHOLD="0.85"
COOLDOWN="0"
SKIP_CATS=""
LOG_DIR="var"
DATE_STAMP="$(date +%Y%m%d_%H%M%S)"
MAIN_LOG="$LOG_DIR/rebuild_all_${DATE_STAMP}.log"
CHECKLIST="$LOG_DIR/rebuild_checklist_${DATE_STAMP}.log"

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)    MODE="--dry-run"; shift ;;
        --threshold)  THRESHOLD="$2"; shift 2 ;;
        --skip)       SKIP_CATS="$2"; shift 2 ;;
        --cooldown)   COOLDOWN="$2"; shift 2 ;;
        *)            echo "Неизвестный аргумент: $1"; exit 1 ;;
    esac
done

mkdir -p "$LOG_DIR"

# Функция для красивого вывода
print_section() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Получить список всех активных категорий
echo -e "${BLUE}📋 Получаю список категорий с офферами...${NC}"
CATEGORIES_LIST=$(python manage.py shell -c "
from apps.products.models import Category
from django.db.models import Count
cats = Category.objects.annotate(c=Count('products__offers')).filter(c__gt=0).order_by('-c')
for cat in cats:
    print(f'{cat.slug}|{cat.c}|{cat.name}')
" 2>/dev/null)

# Считаем общее
TOTAL_CATS=$(echo "$CATEGORIES_LIST" | wc -l)
TOTAL_OFFERS=$(echo "$CATEGORIES_LIST" | awk -F'|' '{sum += $2} END {print sum}')

print_section "🚀 REBUILD_MASTER_PRODUCTS — ЧЕК-ЛИСТ"

echo -e "Режим:       ${YELLOW}${MODE}${NC}"
echo -e "Threshold:   ${YELLOW}${THRESHOLD}${NC}"
echo -e "Cooldown:    ${YELLOW}${COOLDOWN}ч${NC}"
echo -e "Категорий:   ${YELLOW}${TOTAL_CATS}${NC}"
echo -e "Всего офферов: ${YELLOW}${TOTAL_OFFERS}${NC}"
echo -e "Лог:         ${GRAY}${MAIN_LOG}${NC}"
echo -e "Чек-лист:    ${GRAY}${CHECKLIST}${NC}"

if [ -n "$SKIP_CATS" ]; then
    echo -e "Пропустить:  ${YELLOW}${SKIP_CATS}${NC}"
fi

# Состояние ДО
print_section "📊 СОСТОЯНИЕ В БД ДО"
BEFORE_STATS=$(python manage.py shell -c "
from apps.products.models import Product
from django.db.models import Count
multi = Product.objects.annotate(s=Count('offers__source', distinct=True)).filter(s__gte=2).count()
total = Product.objects.count()
print(f'  Products всего:     {total}')
print(f'  Дедуплицировано:    {multi} ({100*multi/total:.2f}%)')
" 2>/dev/null)
echo "$BEFORE_STATS"

# Сохраним в чек-лист
{
    echo "=== REBUILD_MASTER_PRODUCTS — $(date '+%Y-%m-%d %H:%M:%S') ==="
    echo "Mode: $MODE | Threshold: $THRESHOLD | Cooldown: $COOLDOWN"
    echo ""
    echo "ДО:"
    echo "$BEFORE_STATS"
    echo ""
    echo "ЧЕК-ЛИСТ ПО КАТЕГОРИЯМ:"
    echo ""
} > "$CHECKLIST"

# Главный цикл
print_section "🔄 ОБРАБОТКА КАТЕГОРИЙ"

DONE=0
SKIPPED=0
ERRORS=0
TOTAL_CHANGED=0
T_START=$(date +%s)

echo "$CATEGORIES_LIST" | while IFS='|' read -r slug count name; do
    [ -z "$slug" ] && continue

    DONE=$((DONE + 1))

    # Проверяем нужно ли пропустить
    if echo ",$SKIP_CATS," | grep -q ",$slug,"; then
        echo -e "  [${DONE}/${TOTAL_CATS}] ${YELLOW}⏭  $slug${NC} ($count офф)  — ${GRAY}пропущено${NC}"
        echo "[$DONE/$TOTAL_CATS] SKIPPED: $slug ($count офферов)" >> "$CHECKLIST"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    # Прогресс
    T_NOW=$(date +%s)
    ELAPSED=$((T_NOW - T_START))
    echo -ne "  [${DONE}/${TOTAL_CATS}] ${BLUE}⏳ $slug${NC} ($count офф)..."

    # Запускаем rebuild
    TMP_LOG=$(mktemp)
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ALL_PROXY= http_proxy= https_proxy= \
        python manage.py rebuild_master_products \
            $MODE \
            --category "$slug" \
            --threshold "$THRESHOLD" \
            --cooldown-hours "$COOLDOWN" \
            > "$TMP_LOG" 2>&1
    EXIT_CODE=$?

    # Парсим результат
    AUTO_MERGE=$(grep -oE "auto_merge: [0-9]+" "$TMP_LOG" | grep -oE "[0-9]+" || echo "0")
    NEW=$(grep -oE "new: [0-9]+" "$TMP_LOG" | grep -oE "[0-9]+" || echo "0")
    CHANGED=$(grep -oE "product_id изменён у: [0-9]+" "$TMP_LOG" | grep -oE "[0-9]+$" || echo "0")
    DURATION=$(grep -oE "за [0-9]+ с" "$TMP_LOG" | grep -oE "[0-9]+" | head -1 || echo "?")

    # Записываем в общий лог
    {
        echo "═══ $slug ═══"
        cat "$TMP_LOG"
        echo ""
    } >> "$MAIN_LOG"

    if [ "$EXIT_CODE" -eq 0 ]; then
        echo -e "\r  [${DONE}/${TOTAL_CATS}] ${GREEN}✓ $slug${NC} ($count офф) → ${GREEN}auto_merge:$AUTO_MERGE new:$NEW${NC} ${YELLOW}→ изменено $CHANGED${NC} за ${DURATION}с"
        echo "[$DONE/$TOTAL_CATS] OK: $slug ($count офф) auto_merge=$AUTO_MERGE new=$NEW changed=$CHANGED [${DURATION}s]" >> "$CHECKLIST"
        TOTAL_CHANGED=$((TOTAL_CHANGED + CHANGED))
    else
        echo -e "\r  [${DONE}/${TOTAL_CATS}] ${RED}✗ $slug${NC} ${RED}ОШИБКА (exit $EXIT_CODE)${NC}"
        echo "[$DONE/$TOTAL_CATS] ERROR: $slug (exit $EXIT_CODE)" >> "$CHECKLIST"
        ERRORS=$((ERRORS + 1))
    fi

    rm -f "$TMP_LOG"
done

# Финал
T_END=$(date +%s)
TOTAL_TIME=$((T_END - T_START))

print_section "📊 СОСТОЯНИЕ В БД ПОСЛЕ"
AFTER_STATS=$(python manage.py shell -c "
from apps.products.models import Product
from django.db.models import Count
multi = Product.objects.annotate(s=Count('offers__source', distinct=True)).filter(s__gte=2).count()
total = Product.objects.count()
print(f'  Products всего:     {total}')
print(f'  Дедуплицировано:    {multi} ({100*multi/total:.2f}%)')
" 2>/dev/null)
echo "$AFTER_STATS"

print_section "✅ ГОТОВО"
echo -e "Время:        ${YELLOW}${TOTAL_TIME}с${NC} ($(($TOTAL_TIME / 60)) мин)"
echo -e "Категорий:    ${GREEN}${DONE}${NC}"
echo -e "Пропущено:    ${YELLOW}${SKIPPED}${NC}"
echo -e "Ошибок:       ${RED}${ERRORS}${NC}"
echo ""
echo -e "📋 Чек-лист:  ${GRAY}cat ${CHECKLIST}${NC}"
echo -e "📜 Полный лог:${GRAY}cat ${MAIN_LOG}${NC}"

# Сохраняем итог
{
    echo ""
    echo "ПОСЛЕ:"
    echo "$AFTER_STATS"
    echo ""
    echo "Время: ${TOTAL_TIME}с"
} >> "$CHECKLIST"

echo -e "\n${BLUE}=== Содержание чек-листа ===${NC}"
cat "$CHECKLIST"
