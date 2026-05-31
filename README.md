# Price Monitor — агрегатор цен на компьютерные комплектующие

Парсинг товаров с маркетплейсов и магазинов, сравнение офферов по магазинам,
дедупликация в единый master-товар (`Product` + `Offer`) и AI-сравнение характеристик.

**Источники и статус парсеров:**

| Источник | Статус | Команда / задача |
|---|---|---|
| **DNS** | ✅ работает | `parse_dns` / `task_parse_category` |
| **Citilink** | ✅ работает | `parse_citilink` / `task_parse_citilink_category` |
| **Wildberries** | ✅ работает | `parse_wildberries` / `task_parse_wb_category` |
| **Ozon** | ⚠️ почти настроен, парсит некорректно | `parse_ozon` / `task_parse_ozon_category` |
| **Regard** | ⚠️ почти настроен, не запускается | `task_parse_regard_category` (нет `regard_parser.py`) |

> Ozon и Regard в работе. Ozon-парсер (`ozon_parser.py` + `ozon_composer.py`)
> и команда `parse_ozon` есть, но выдаёт неполные/некорректные данные.
> Regard объявлен в источниках и задачах (`task_parse_regard_category` импортирует
> `.regard_parser`), но сам модуль парсера ещё не реализован — задача упадёт на импорте.

## Стек технологий

### Backend
- **Framework**: Django 5, Django REST Framework
- **Очереди задач**: Celery 5 + RabbitMQ
- **База данных**: PostgreSQL 17 на образе **TimescaleDB** (hypertable на `PriceHistory`) + расширение **pgvector** (HNSW индекс на `Product.match_embedding`)
- **Кэш / брокер результатов**: Redis 7
- **Парсинг**: Selenium + undetected-chromedriver (Chrome)
- **Семантический матчинг**: sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim)
- **AI-сравнение**: Google Gemini API (`gemini-2.0-flash`)
- **Контейнеризация**: Docker, Docker Compose

### Frontend
- **Framework**: React 18 + Vite + TypeScript
- **Данные**: TanStack React Query
- **State**: Zustand
- **UI**: Radix UI primitives + Tailwind CSS
- **Графики**: Recharts
- **Анимации**: Framer Motion
- **Роутинг**: React Router

Страницы: каталог, карточка товара, сравнение, дашборд, wishlist, подписки,
уведомления, сборка ПК (Builder), вход/регистрация. Дизайн-бриф — в `CLAUDE.md`.

### Требования к Postgres

В docker-compose используется образ `timescale/timescaledb-ha:pg17` — он включает
**и TimescaleDB, и pgvector**, оба расширения ставятся автоматически. Если поднимаешь
Postgres сам, поставь оба расширения (`vector`, `timescaledb`).

- Расширение `vector` активируется миграцией `0012_install_pgvector_and_embedding_col`
  (`CREATE EXTENSION IF NOT EXISTS vector`). Без него `migrate` упадёт на этой миграции.
- TimescaleDB-hypertable и retention-политики настраиваются командой
  `python manage.py setup_timescaledb` (управляется `TIMESCALE_ENABLED`,
  `TIMESCALE_RETENTION_DAYS` в `.env`).

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd try2cursach
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
# Отредактируйте .env — укажите SECRET_KEY, пароли БД и GEMINI_API_KEY (для AI-сравнения)
```

### 3. Запустить через Docker Compose

```bash
docker-compose up --build
```

Базовый набор сервисов:
- **PostgreSQL (TimescaleDB)** на порту 5432
- **RabbitMQ** на порту 5672 (управление: 15672)
- **Redis** на порту 6379
- **web** — Django (gunicorn) на порту 8000 (на старте делает `migrate` + `seed_categories --update`)
- **frontend** — собранный React-фронт за nginx на порту 80

Celery (`celery-worker`, `celery-beat`) вынесены в профиль `docker-celery`
(требуют Chrome и больше памяти):

```bash
docker-compose --profile docker-celery up --build
```

Альтернатива — запуск Celery worker на хосте через `scripts/run_celery_worker.sh`
(ходит на проброшенные порты Docker; хосты в `.env` по умолчанию `localhost`).

### 4. Создать суперпользователя

```bash
docker-compose exec web python manage.py createsuperuser
# или локально (venv активирован):
python manage.py createsuperuser
```

### 5. Категории

`web` на старте автоматически прогоняет `seed_categories --update`. Вручную:

```bash
docker-compose exec web python manage.py seed_categories
# повторный запуск не дублирует (тот же slug); --update перезапишет название и пути
```

Свои категории — JSON-массив объектов `{"name","slug","dns_category_slug"}`:

```bash
python manage.py seed_categories --file apps/products/fixtures/my_categories.json
```

Привязки к источникам хранятся в `CategoryListing` (по одной на источник: DNS,
Citilink, Ozon, WB, Regard). Утилиты валидации/обнаружения листингов:
`citilink_validate_listings`, `ozon_validate_listings`, `ozon_discover_listings`,
`wb_resolve_categories`.

### 6. Запустить парсинг вручную

```bash
# DNS — все активные категории
docker-compose exec web python manage.py parse_dns

# Конкретная категория, синхронно (без Celery, логи в консоль)
docker-compose exec web python manage.py parse_dns --category operativnaya-pamyat --sync

# Другие источники
python manage.py parse_citilink --sync
python manage.py parse_wildberries --category videokarty --sync
python manage.py parse_ozon --sync          # ⚠️ результат пока некорректный
```

Без `--sync` задачи уходят в Celery (нужен worker).

**Chrome без окна:** `CHROME_HEADLESS=1` в `.env` или флаг `--headless`/`--no-headless`
у команды. У DNS headless иногда отдаёт **403** — тогда `CHROME_HEADLESS=0`.
Задачи Celery используют значение из `.env` при старте worker (флаги команды на очередь не влияют).

## API эндпоинты

Базовый префикс — `/api/`. Аутентификация — сессионная (DRF), CSRF-exempt для API.

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/products/` | Список товаров (фильтры, пагинация) |
| GET | `/api/products/{id}/` | Детали товара (с историей цен) |
| GET | `/api/products/{id}/price-history/` | История цен товара |
| GET | `/api/families/` | Семейства товаров (`ProductFamily`) |
| GET | `/api/categories/` | Категории |
| GET | `/api/categories/{slug}/facets/` | Фасеты категории для фильтров |
| GET | `/api/offers/` | Офферы (цены по магазинам) |
| GET/POST/DELETE | `/api/subscriptions/` | Подписки на цену |
| GET/PATCH | `/api/notifications/` | Уведомления |
| GET/POST/DELETE | `/api/wishlist/` | Wishlist |
| GET | `/api/dashboard/` | Сводка для дашборда |
| GET/POST | `/api/compare/` | Сравнение товаров |
| POST | `/api/compare/ai-summary/` | AI-вердикт по сравнению (Gemini) |
| POST | `/api/auth/register/` · `/login/` · `/logout/`, GET `/auth/me/` | Аутентификация |

## Периодические задачи (Celery Beat)

| Задача | Расписание |
|---|---|
| Парсинг всех DNS-категорий (`task_parse_all_categories`) | Каждые 6 часов |
| Проверка подписок | Каждый час |
| Очистка зависших `ParseRun` | Каждые 15 минут |
| Purge `MergeAuditLog` | Воскресенье 04:00 |

> Детекция аномалий и `ENABLE_ADVANCED_ANALYTICS` удалены. Аналитика теперь — это
> сравнение товаров, AI-вердикт, лучшие предложения, индекс цен, тепловые карты и снимки
> (`apps/analytics/`), без отдельного фоново-аномального пайплайна.

## Тесты

```bash
docker-compose exec web pytest -v
```

## Dedupe V2: операционный чеклист

Дедупликация v2 (MPN + specs + scoring + эмбеддинги) включена по умолчанию
(`DEDUP_V2=1`). Legacy Dice-по-имени остаётся fallback-веткой.

### 1) Подготовка и бэкфилл фич (без merge)

```bash
python manage.py rebuild_features --dry-run
python manage.py rebuild_features --apply
```

### 2) Shadow-прогон (без изменения product_id)

- `DEDUP_SHADOW=1`, `DEDUP_V2=0`, дать поработать 1–3 дня на обычном парсинге.
- Отчёт: `python manage.py audit_dedup --days 3 --sample-size 50`

### 3) Ручной one-shot rebuild мастеров

```bash
python manage.py rebuild_master_products --dry-run --threshold 0.85 --cooldown-hours 24
python manage.py rebuild_master_products --apply  --threshold 0.85 --cooldown-hours 24
python manage.py rebuild_master_products --rollback <run_id>   # rollback по run_id из вывода
```

### 4) Переключение на v2

- `DEDUP_SHADOW=0`, `DEDUP_V2=1`.

### 5) Ежедневный KPI-мониторинг

```bash
python manage.py audit_dedup --days 7 --sample-size 50
```

Ключевые метрики: `cross_source_coverage`, `merge_error_rate` (цель < 1%, alert > 2%),
`review_queue_depth` (< 200), `silent_orphans` (0), `hard_reject_rate`.

### Что уже усилено в коде

- GIN индекс на `Product.specs_fingerprint`, HNSW на `Product.match_embedding`.
- Транзитивная защита перед merge (проверка конфликтов на сэмплах офферов).
- Cooldown-защита в `rebuild_master_products` (по умолчанию 24 часа).

Связанные команды: `rebuild_embeddings`, `rebuild_product_families`,
`rebuild_product_mpn`, `cluster_similar_products`, `merge_duplicate_products`.

## Структура проекта

```
try2cursach/
├── config/                 # Django settings, Celery, beat-schedule
├── apps/
│   ├── core/               # User, management-команды parse_* (dns/citilink/ozon/wildberries)
│   ├── products/           # Category, CategoryListing, ProductFamily, Product, Offer, dedupe/
│   ├── prices/             # PriceHistory, парсеры (DNS, Citilink, Ozon, WB), TimescaleDB
│   ├── alerts/             # Подписки на цену, уведомления
│   ├── analytics/          # Сравнение, AI-вердикт (Gemini), best deals, price index, heatmap
│   └── api/                # REST API (DRF)
├── frontend/               # React + Vite + TS (за nginx в Docker)
├── templates/              # Server-side UI каталога и карточки (legacy)
├── docs/                   # DEPLOY_AND_MIGRATE.md и др.
├── scripts/                # run_celery_worker.sh, миграции volume и т.п.
├── docker/                 # Dockerfile.web, Dockerfile.celery
└── docker-compose.yml
```

Локально (не в git): `var/chrome_profiles/` — профили Chrome для anti-bot.

**Парсеры (`apps/prices/`):** `parsers.py` (DNS), `citilink_parser.py`,
`ozon_parser.py` + `ozon_composer.py`, `wildberries_parser.py`,
`base_parser.py` (общая логика Chrome/Selenium). `regard_parser.py` — TODO.
