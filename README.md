Агрегатор цен на компьютерные комплектующие: парсинг **DNS**, **Citilink**, **Ozon**,
сравнение офферов по магазинам и дедупликация в единый master-товар (`Product` + `Offer`).

Опционально: детекция аномалий в ценах (`ENABLE_ADVANCED_ANALYTICS=1`).

## Стек технологий

- **Backend**: Django 5, Django REST Framework 3.15
- **Очереди задач**: Celery 5.4 + RabbitMQ
- **База данных**: PostgreSQL 15 + расширение **pgvector** (HNSW индекс на `Product.match_embedding`)
- **Кэш**: Redis 7
- **Парсинг**: Selenium + undetected-chromedriver
- **Семантический матчинг**: sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim)
- **Аналитика**: NumPy, SciPy (FFT для детекции циклов)
- **Контейнеризация**: Docker, Docker Compose

### Требования к Postgres

В docker-compose используется образ `pgvector/pgvector:pg15` — расширение
`vector` ставится автоматически. Если поднимаешь Postgres сам (Linux/Windows):

```bash
# Ubuntu / Debian
sudo apt install postgresql-15-pgvector

# Windows — собрать из исходников (нужны Visual Studio Build Tools):
# https://github.com/pgvector/pgvector#windows
```

Расширение активируется автоматически миграцией `0012_install_pgvector_*`
(`CREATE EXTENSION IF NOT EXISTS vector`). Без него `manage.py migrate`
упадёт на этой миграции.

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd price_monitor
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
# Отредактируйте .env — укажите SECRET_KEY и пароли
```

### 3. Запустить через Docker Compose

```bash
docker-compose up --build
```

Это поднимет:
- **PostgreSQL** на порту 5432
- **RabbitMQ** на порту 5672 (управление: 15672)
- **Redis** на порту 6379
- **Django** (gunicorn) на порту 8000
- **Celery Worker** (с Chrome для парсинга)
- **Celery Beat** (планировщик периодических задач)

### 4. Создать суперпользователя

```bash
docker-compose exec web python manage.py createsuperuser
```

Без Docker (локально, venv активирован): `python manage.py createsuperuser`.

### 5. Добавить категории

**Вариант A — одной командой** (ОЗУ, мониторы, видеокарты, БП, процессоры, материнки, SSD, HDD 3.5", корпуса):

```bash
docker-compose exec web python manage.py seed_categories
# или локально:
python manage.py seed_categories
```

Повторный запуск не дублирует записи (те же `slug`). Чтобы перезаписать название и путь DNS у существующих: `python manage.py seed_categories --update`.

Свои категории — JSON-массив `{"name","slug","dns_category_slug"}` (путь — как в URL после `https://www.dns-shop.ru/catalog/` без начального и конечного `/`):

```bash
python manage.py seed_categories --file apps/products/fixtures/my_categories.json
```

**Вариант B — вручную** в Django Admin (`http://localhost:8000/admin/`):

| Название | Slug | DNS Category Slug |
|---|---|---|
| Оперативная память | operativnaya-pamyat | 17a89a3916404e77/operativnaya-pamyat |
| Мониторы | monitory | 17a8943d16404e77/monitory |
| Материнские платы | materinskie-platy | 17a89a0416404e77/materinskie-platy |
| SSD-накопители | ssd-nakopiteli | 8a9ddfba20724e77/ssd-nakopiteli |
| Жёсткие диски 3.5" | zhestkie-diski-35 | 17a8914916404e77/zestkie-diski-3.5 |
| Корпуса | korpusa | 17a89c5616404e77/korpusa |

### 6. Запустить парсинг вручную

```bash
# Через management-команду
docker-compose exec web python manage.py parse_dns

# Или для конкретной категории (синхронно)
docker-compose exec web python manage.py parse_dns --category operativnaya-pamyat --sync
```

Локально (Windows): `python manage.py parse_dns --sync` — все активные категории по очереди; без `--sync` задачи уходят в Celery (нужен worker).

**Chrome без окна:** в `.env` задайте `CHROME_HEADLESS=1` или один раз: `python manage.py parse_dns --sync --headless`. У DNS иногда даёт **403** в headless; тогда оставьте `CHROME_HEADLESS=0` или `--no-headless`. Задачи **Celery** используют значение из `.env` при старте worker (флаги команды на очередь не влияют).

## API Эндпоинты

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/products/` | Список товаров |
| GET | `/api/products/{id}/` | Детали товара (с историей цен) |
| GET | `/api/products/{id}/price-history/` | История цен товара |
| GET | `/api/subscriptions/` | Подписки текущего пользователя |
| POST | `/api/subscriptions/` | Создать подписку |
| DELETE | `/api/subscriptions/{id}/` | Удалить подписку |
| GET | `/api/anomalies/` | Аномалии (если `ENABLE_ADVANCED_ANALYTICS=1`) |

## Периодические задачи (Celery Beat)

| Задача | Расписание |
|---|---|
| Парсинг всех категорий | Каждые 6 часов |
| Проверка подписок | Каждый час |
| Очистка зависших ParseRun | Каждые 15 минут |
| Purge MergeAuditLog (UPDATE) | Воскресенье 04:00 |
| Детекция аномалий | Ежедневно 03:00 — **только при `ENABLE_ADVANCED_ANALYTICS=1`** |

## Тесты

```bash
docker-compose exec web pytest -v
```

## Dedupe V2: операционный чеклист

Короткий безопасный порядок запуска новой дедупликации в проде/стейдже.

### 1) Подготовка и бэкфилл фич (без merge)

```bash
# dry-run
python manage.py rebuild_features --dry-run

# apply
python manage.py rebuild_features --apply
```

### 2) Shadow-прогон (без изменения product_id)

- Включить `DEDUP_SHADOW=True`, `DEDUP_V2=False`.
- Дать поработать 1-3 дня на обычном парсинге.
- Проверять отчёт:

```bash
python manage.py audit_dedup --days 3 --sample-size 50
```

### 3) Ручной one-shot rebuild мастеров

```bash
# оценка изменений
python manage.py rebuild_master_products --dry-run --threshold 0.85 --cooldown-hours 24

# применение
python manage.py rebuild_master_products --apply --threshold 0.85 --cooldown-hours 24

# rollback по run_id (из вывода команды)
python manage.py rebuild_master_products --rollback <run_id>
```

### 4) Переключение на v2

- Выключить shadow, включить v2:
  - `DEDUP_SHADOW=False`
  - `DEDUP_V2=True`
- Legacy остаётся fallback-веткой на случай исключений.

### 5) Ежедневный KPI-мониторинг

```bash
python manage.py audit_dedup --days 7 --sample-size 50
```

Смотреть в первую очередь:
- `cross_source_coverage`
- `merge_error_rate` (целевой < 1%, alert > 2%)
- `review_queue_depth` (целевой < 200)
- `silent_orphans` (целевой 0)
- `hard_reject_rate` (без резких скачков)

### Что уже усилено в коде

- GIN индекс на `Product.specs_fingerprint`.
- Транзитивная защита перед merge (проверка конфликтов на сэмплах офферов).
- Cooldown-защита в `rebuild_master_products` (по умолчанию 24 часа).

## Структура проекта

```
price_monitor/
├── config/             # Django, Celery
├── apps/
│   ├── core/           # User, management-команды parse_*
│   ├── products/       # Category, Product, Offer, dedupe/
│   ├── prices/         # PriceHistory, парсеры DNS/Citilink/Ozon
│   ├── alerts/         # Подписки на цену
│   ├── analytics/      # Опционально: Anomaly, прогнозы, снимки
│   └── api/            # REST API
├── templates/          # UI каталога и карточки товара
├── docs/               # DEPLOY_AND_MIGRATE.md
├── docker/
└── docker-compose.yml
```

Локально (не в git): `var/chrome_profiles/` — профили Chrome для anti-bot.
