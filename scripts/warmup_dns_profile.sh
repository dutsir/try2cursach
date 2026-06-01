#!/usr/bin/env bash
# Прогрев Chrome-профиля для DNS-парсера.
#
# Идея: запускаем Chrome с РЕАЛЬНЫМ окном на видимом дисплее,
# даём пользователю вручную пройти Qrator challenge,
# Chrome сохраняет cookies и историю в профиле.
# Потом парсер использует ЭТОТ же профиль через Xvfb,
# Qrator уже знает этого "пользователя" и не блокирует.
#
# Запуск:
#   ./scripts/warmup_dns_profile.sh
#
# После того как страница DNS загрузится в Chrome:
# 1) походи по сайту 1-2 минуты (открой пару категорий, товаров)
# 2) закрой Chrome
# 3) теперь профиль "прогрет" — парсер сможет им пользоваться

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_DIR="${PROFILE_DIR:-$PROJECT_DIR/var/chrome_profiles/dns}"

mkdir -p "$PROFILE_DIR"

# Снимаем stale Singleton-локи. Их оставляет упавший Chrome, а в Docker —
# контейнерный Chrome (lock содержит hostname контейнера). Хостовый Chrome видит
# «чужой» hostname и отказывается стартовать («profile in use on another computer»).
rm -f "$PROFILE_DIR"/Singleton* 2>/dev/null || true

echo "🔥 Прогреваю Chrome-профиль для DNS"
echo "    Профиль: $PROFILE_DIR"
echo ""
echo "Что делать:"
echo "1. Откроется обычное окно Chrome"
echo "2. Зайди на https://www.dns-shop.ru/ (или открой главную)"
echo "3. Если Qrator показывает капчу — пройди её (один клик обычно)"
echo "4. Походи по сайту: открой пару категорий, кликни на товар"
echo "5. Закрой окно Chrome когда закончишь"
echo ""
echo "Эти действия научат Qrator что ты живой пользователь."
echo "Cookies сохранятся в профиле, парсер ими воспользуется."
echo ""

# Используем твой РЕАЛЬНЫЙ дисплей, не Xvfb
# (если ты в SSH без X — нужно поменять на :99 и пройти Qrator через VNC)
unset DISPLAY
export DISPLAY="${REAL_DISPLAY:-:0}"

echo "DISPLAY=$DISPLAY"

# Запускаем Chrome с user-data-dir на этот профиль
google-chrome \
  --user-data-dir="$PROFILE_DIR" \
  --window-size=1920,1080 \
  --no-first-run \
  --no-default-browser-check \
  https://www.dns-shop.ru/ &

CHROME_PID=$!

echo ""
echo "Chrome запущен (PID: $CHROME_PID)"
echo "Когда закончишь — закрой окно Chrome (Ctrl+W или крестик)"
echo "Скрипт автоматически дождётся завершения Chrome."

wait "$CHROME_PID"

echo ""
echo "✓ Chrome закрыт. Профиль прогрет."
echo ""
echo "Проверка содержимого профиля:"
du -sh "$PROFILE_DIR" 2>/dev/null || echo "Не удалось проверить размер"
ls "$PROFILE_DIR/Default" 2>/dev/null | head -5 || true

echo ""
echo "🎉 Готово. Парсер теперь будет использовать этот профиль."
echo "Запусти парсинг:"
echo "    source venv/bin/activate"
echo "    python manage.py shell"
echo "    >>> from apps.prices.tasks import task_parse_category"
echo "    >>> from apps.products.models import Category"
echo "    >>> cat = Category.objects.filter(listings__source='dns', listings__is_active=True).distinct().first()"
echo "    >>> task_parse_category.delay(cat.id)"
