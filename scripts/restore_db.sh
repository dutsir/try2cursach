#!/usr/bin/env bash
# Восстановление БД price_monitor из бинарного дампа (созданного scripts/dump_db.ps1).
#
# Поддерживает TimescaleDB-safe restore (через timescaledb_pre_restore /
# timescaledb_post_restore) и pgvector.
#
# Использование:
#   ./scripts/restore_db.sh <path-to-dump-file>
#
# Параметры берутся из .env или DB_* env variables.
set -euo pipefail

DUMP_FILE="${1:-}"
if [ -z "$DUMP_FILE" ]; then
    echo "Usage: $0 <path-to-dump-file>"
    exit 1
fi
if [ ! -f "$DUMP_FILE" ]; then
    echo "Файл не найден: $DUMP_FILE"
    exit 1
fi

# Загружаем .env если есть
if [ -f .env ]; then
    set -a; source .env; set +a
fi

CONTAINER="${DB_CONTAINER:-pm_postgres}"
DB_NAME="${DB_NAME:-price_monitor}"
DB_USER="${DB_USER:-pm_user}"

# Проверка что контейнер запущен
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "Контейнер ${CONTAINER} не запущен. Подними его: docker-compose up postgres -d"
    exit 1
fi

# Копируем dump внутрь контейнера (медленнее, но не зависит от volume mount)
echo "[1/6] Копирую дамп в контейнер…"
docker cp "$DUMP_FILE" "${CONTAINER}:/tmp/restore.dump"

# DROP + CREATE базы (полный wipe для чистого restore)
echo "[2/6] Пересоздаю БД ${DB_NAME}…"
docker exec -u postgres "$CONTAINER" psql -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker exec -u postgres "$CONTAINER" psql -d postgres -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

# Устанавливаем расширения ДО restore
echo "[3/6] Устанавливаю расширения (timescaledb, vector)…"
docker exec -u postgres "$CONTAINER" psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
docker exec -u postgres "$CONTAINER" psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# TimescaleDB pre-restore: переводит расширение в режим обновления метаданных
echo "[4/6] timescaledb_pre_restore()…"
docker exec -u postgres "$CONTAINER" psql -d "$DB_NAME" -c "SELECT timescaledb_pre_restore();"

# pg_restore с custom format
echo "[5/6] pg_restore (это самый долгий шаг)…"
docker exec -u postgres "$CONTAINER" pg_restore \
    --dbname="$DB_NAME" \
    --no-owner --no-acl \
    --exit-on-error \
    /tmp/restore.dump

# TimescaleDB post-restore: возвращает hypertables в боевой режим
echo "[6/6] timescaledb_post_restore()…"
docker exec -u postgres "$CONTAINER" psql -d "$DB_NAME" -c "SELECT timescaledb_post_restore();"

# Чистим временный файл
docker exec "$CONTAINER" rm -f /tmp/restore.dump

# Краткая проверка
echo ""
echo "=== Sanity check ==="
docker exec -u postgres "$CONTAINER" psql -d "$DB_NAME" -c "
    SELECT
        (SELECT COUNT(*) FROM products_product)        AS products,
        (SELECT COUNT(*) FROM products_productfamily)  AS families,
        (SELECT COUNT(*) FROM products_offer)          AS offers,
        (SELECT COUNT(*) FROM prices_pricehistory)     AS prices;
"

echo ""
echo "OK: restore завершён."
echo "Дальше: docker-compose up -d  (поднимет web/celery, миграции уже накатаны)"
