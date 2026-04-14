Система мониторинга цен на компьютерные комплектующие (ОЗУ, мониторы) с сайта DNS
с модулем детекции аномалий в ценообразовании.

## Стек технологий

- **Backend**: Django 5, Django REST Framework 3.15
- **Очереди задач**: Celery 5.4 + RabbitMQ
- **База данных**: PostgreSQL 15
- **Кэш**: Redis 7
- **Парсинг**: Selenium + undetected-chromedriver
- **Аналитика**: NumPy, SciPy (FFT для детекции циклов)
- **Контейнеризация**: Docker, Docker Compose

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
| GET | `/api/anomalies/` | Обнаруженные аномалии |

## Периодические задачи (Celery Beat)

| Задача | Расписание |
|---|---|
| Парсинг всех категорий | Каждые 6 часов |
| Проверка подписок | Каждый час |
| Детекция аномалий | Ежедневно в 03:00 |

## Тесты

```bash
docker-compose exec web pytest -v
```

## Структура проекта

```
price_monitor/
├── config/             # Настройки Django, Celery
├── apps/
│   ├── core/           # User, BaseModel
│   ├── products/       # Category, Product
│   ├── prices/         # PriceHistory, DNSParser, задачи парсинга
│   ├── alerts/         # Subscription, Notification
│   ├── analytics/      # Anomaly, detector (spike/manipulation/cyclic)
│   └── api/            # DRF ViewSets, serializers
├── docker/             # Dockerfiles
└── docker-compose.yml
```
