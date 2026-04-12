# Деплой на сервер и перенос данных с локального ПК

Репозиторий: [try2cursach](https://github.com/dutsir/try2cursach).

## Что понадобится

- Сервер Ubuntu с Docker и Docker Compose v2
- SSH-доступ (`root` или пользователь с `sudo`)
- На ноутбуке: установленный **PostgreSQL client** (`pg_dump`) или доступ к той же БД, что использует Django локально

---

## Часть 1. Дамп базы на ноутбуке (Windows)

Локально у вас в `.env` обычно что-то вроде:

- `DB_NAME=curcash`
- `DB_USER=postgres`
- `DB_HOST=localhost`
- `DB_PORT=5432`

### Вариант A: PostgreSQL установлен локально (служба на Windows)

В PowerShell (из папки, где лежит `pg_dump`, или добавьте его в PATH):

```powershell
cd $env:USERPROFILE
# Путь к pg_dump может быть, например:
# "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"

& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -Fc -U postgres -h localhost -p 5432 -d curcash -f "$env:USERPROFILE\Desktop\curcash_local.dump"
```

Пароль спросит интерактивно (как в `.env` у `DB_PASSWORD`).

### Вариант B: если база только в Docker на ПК

Найдите имя контейнера Postgres:

```powershell
docker ps
```

Затем:

```powershell
docker exec -i <имя_контейнера_postgres> pg_dump -Fc -U <user> <db_name> > $env:USERPROFILE\Desktop\curcash_local.dump
```

Файл `curcash_local.dump` положите в удобное место (например Рабочий стол).

---

## Часть 2. Сервер: клонирование и первый запуск

Подключитесь по SSH:

```bash
ssh root@<IP_сервера>
```

Установите Docker (если ещё нет):

```bash
apt update && apt install -y docker.io docker-compose-v2 git
docker --version
```

Клонируйте репозиторий:

```bash
cd /opt
git clone https://github.com/dutsir/try2cursach.git price_monitor
cd price_monitor
```

Создайте `.env` из примера и **задайте свои секреты**:

```bash
cp .env.example .env
nano .env
```

Обязательно проверьте для Docker:

- `DB_HOST=postgres` (не `localhost`)
- `DB_NAME=price_monitor` (или оставьте как в `.env.example`)
- `DB_USER=pm_user`, `DB_PASSWORD` — совпадают с тем, что будет в `docker-compose` (по умолчанию из примера)
- `RABBITMQ_HOST=rabbitmq`, `REDIS_HOST=redis`
- `ALLOWED_HOSTS` — IP или домен сервера
- `DEBUG=0`
- `SECRET_KEY` — новый длинный случайный ключ
- `CHROME_HEADLESS=1` на сервере без GUI

Поднимите стек (первый раз соберёт образы):

```bash
docker compose up -d --build
```

Дождитесь, пока `postgres` станет healthy. Проверка:

```bash
docker compose ps
```

---

## Часть 3. Перенос дампа на сервер

На **ноутбуке** (PowerShell) файл дампа может лежать в папке проекта, например:

`C:\sem6\cursach\price_monitor\curcash_local.dump`

Подставьте свой IP сервера и пользователя SSH:

```powershell
scp "C:\sem6\cursach\price_monitor\curcash_local.dump" root@<IP_сервера>:/opt/price_monitor/
```

Пример с реальным IP (замените на свой):

```powershell
scp "C:\sem6\cursach\price_monitor\curcash_local.dump" root@31.13.208.78:/opt/price_monitor/
```

Если дамп на рабочем столе:

```powershell
scp "$env:USERPROFILE\Desktop\curcash_local.dump" root@<IP_сервера>:/opt/price_monitor/
```

Кавычки вокруг пути нужны, если в нём есть пробелы.

---

## Часть 4. Восстановление дампа в контейнер Postgres

На сервере:

```bash
cd /opt/price_monitor
```

Остановите контейнеры, которые держат соединения с БД (чтобы не было конфликтов):

```bash
docker compose stop web celery-worker celery-beat
```

**Важно:** локальная БД называлась `curcash`, в Docker по умолчанию — `price_monitor` (из `.env`). Дамп нужно залить в **целевую** БД контейнера.

```bash
docker exec -i pm_postgres pg_restore --clean --if-exists -U pm_user -d price_monitor < curcash_local.dump
```

Если ошибка «database does not exist» — создайте БД один раз:

```bash
docker exec -it pm_postgres psql -U pm_user -d postgres -c "CREATE DATABASE price_monitor OWNER pm_user;"
```

Повторите `pg_restore`.

Если ошибки про «owner» или расширения — пришлите текст; часто помогает предварительно `migrate` на пустой БД и затем restore только данных (сложнее). Для курсовой чаще всего хватает полного restore на **пустой** том Postgres (первый деплой без важных данных).

После успешного restore:

```bash
docker compose up -d
```

Суперпользователь Django:

```bash
docker compose exec web python manage.py createsuperuser
```

Проверка количества записей:

```bash
docker compose exec web python manage.py shell -c "from apps.products.models import Product; from apps.prices.models import PriceHistory; print(Product.objects.count(), PriceHistory.objects.count())"
```

---

## Часть 5. Проверка Celery (парсинг не параллелит категории)

В образе воркера задано **`--concurrency=1`**: одновременно выполняется одна задача парсинга.

В `.env` держите:

```env
CELERY_DNS_CATEGORY_PAUSE_SECONDS=180
```

Тогда `task_parse_all_categories` идёт **цепочкой** с паузой между категориями.

Логи воркера:

```bash
docker compose logs -f celery-worker
```

---

## Часть 6. Бэкап на сервере (чтобы не потерять данные)

```bash
chmod +x scripts/backup.sh
# при необходимости задайте переменные в crontab
```

Пример cron (каждый день в 3:00):

```cron
0 3 * * * /opt/price_monitor/scripts/backup.sh >> /var/log/pm_backup.log 2>&1
```

---

## Часть 7. Обновление кода после изменений на ноутбуке

```bash
cd /opt/price_monitor
git pull
docker compose build
docker compose run --rm web python manage.py migrate
docker compose up -d
```

---

## Типичные проблемы

| Симптом | Что сделать |
|--------|-------------|
| `pg_dump` не найден на Windows | Установите PostgreSQL с [официального сайта](https://www.postgresql.org/download/windows/) или используйте `docker exec` из контейнера с Postgres |
| После restore админка не логинится | Создайте `createsuperuser` заново или сбросьте пароль |
| Ошибки миграций после restore | Дамп и код должны быть с одной версии миграций; сначала `git pull` на том же коммите, что и локально, потом restore |
| Парсер падает по таймауту | См. `CHROME_HEADLESS`, паузы, VPN/прокси при необходимости |

---

## Краткий чеклист

1. [ ] Локально: `pg_dump -Fc` → `curcash_local.dump`
2. [ ] `scp` файла на сервер
3. [ ] Сервер: `git clone`, `.env`, `docker compose up -d --build`
4. [ ] `docker compose stop web celery-worker celery-beat`
5. [ ] `pg_restore` в `pm_postgres` → БД `price_monitor`
6. [ ] `docker compose up -d`, `createsuperuser`, проверка counts
7. [ ] Настроить cron бэкапа
