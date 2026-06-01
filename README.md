# Price Monitor — агрегатор цен на компьютерные комплектующие

Сбор товаров с маркетплейсов и магазинов, сравнение офферов, дедупликация в единый товар (Product + Offer), AI-сравнение характеристик.

## Источники

- DNS (работает)
- Citilink (работает)
- Wildberries (работает)
- Ozon (в процессе — парсер выдаёт неполные данные)
- МВидео(работает)

## Стек

**Backend**
- Django 5, Django REST Framework
- Celery 5, RabbitMQ
- PostgreSQL 17 (TimescaleDB + pgvector)
- Redis 7
- Selenium + undetected-chromedriver
- sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2, 384-мерные эмбеддинги)
- Google Gemini API (gemini-2.0-flash)
- Docker, Docker Compose

**Frontend**
- React 18, Vite, TypeScript
- TanStack React Query, Zustand
- Radix UI, Tailwind CSS
- Recharts, Framer Motion, React Router

Страницы: каталог, карточка товара, сравнение, дашборд, wishlist, подписки, уведомления, сборка ПК (Builder), вход/регистрация.

## Основные возможности

- Сбор цен и характеристик с нескольких источников
- Объединение офферов в мастер-товары с помощью дедупликации (Dice + MPN/specs/эмбеддинги)
- Семантический поиск и подбор аналогов (pgvector HNSW)
- AI-сравнение товаров (через Gemini)
- История цен (TimescaleDB hypertable)
- Подписки на изменение цены, уведомления, wishlist
- Дашборд с аналитикой (лучшие предложения, индекс цен, тепловые карты)

## API (основные эндпоинты)

Префикс `/api/`, аутентификация сессионная.

- `GET /products/` — список товаров
- `GET /products/{id}/` — карточка товара
- `GET /products/{id}/price-history/` — история цен
- `GET /families/` — семейства товаров
- `GET /categories/`, `GET /categories/{slug}/facets/`
- `GET /offers/`
- `GET/POST/DELETE /subscriptions/`
- `GET/PATCH /notifications/`
- `GET/POST/DELETE /wishlist/`
- `GET /dashboard/`
- `GET/POST /compare/`, `POST /compare/ai-summary/`
- `POST /auth/register/`, `/login/`, `/logout/`, `GET /auth/me/`

## Периодические задачи (Celery Beat)

- Парсинг всех категорий — раз в 24 часов
- Проверка подписок — раз в час
- Очистка зависших ParseRun — каждые 15 минут
- Очистка MergeAuditLog — раз в 24ч 

try2cursach/
├── config/ # Настройки Django, Celery, расписание
├── apps/
│ ├── core/ # Управление пользователями, management-команды парсинга
│ ├── products/ # Категории, товары, семейства, дедупликация
│ ├── prices/ # История цен, парсеры (DNS, Citilink, Ozon, WB, base)
│ ├── alerts/ # Подписки, уведомления
│ ├── analytics/ # Сравнение, AI-вердикт, best deals, price index, heatmap
│ └── api/ # REST API (DRF)
├── frontend/ # React-приложение
├── scripts/ # Вспомогательные скрипты
├── docker/ # Dockerfile'ы
└── docker-compose.yml

