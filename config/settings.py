import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(encoding='utf-8')

os.environ.setdefault('PGCLIENTENCODING', 'UTF8')

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')

DEBUG = os.getenv('DEBUG', '0') == '1'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = [
    x.strip()
    for x in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost:5173,http://localhost:8000,http://127.0.0.1:5173,http://127.0.0.1:8000',
    ).split(',')
    if x.strip()
]

# На проде задать CORS_ALLOWED_ORIGINS=https://example.com (через запятую).
# Дефолт — localhost для dev.
CORS_ALLOWED_ORIGINS = [
    x.strip()
    for x in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost,http://localhost:5173,http://localhost:8000,'
        'http://127.0.0.1,http://127.0.0.1:5173,http://127.0.0.1:8000',
    ).split(',')
    if x.strip()
]

CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'apps.core',
    'apps.products',
    'apps.prices',
    'apps.alerts',
    'apps.builds',
    'apps.analytics',
    'apps.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise отдаёт /static/ при DEBUG=0 (админка, DRF browsable API).
    # Должен идти сразу после SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'price_monitor'),
        'USER': os.getenv('DB_USER', 'pm_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'pm_secret'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'options': '-c client_encoding=UTF8',
        },
    }
}

AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise: сжатие + хэш-манифест для статики в проде.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.api.authentication.CsrfExemptSessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

_default_celery_broker = (
    f"amqp://{os.getenv('RABBITMQ_USER', 'guest')}:"
    f"{os.getenv('RABBITMQ_PASS', 'guest')}@"
    f"{os.getenv('RABBITMQ_HOST', 'localhost')}:"
    f"{os.getenv('RABBITMQ_PORT', '5672')}//"
)
_default_celery_redis = (
    f"redis://{os.getenv('REDIS_HOST', 'localhost')}:"
    f"{os.getenv('REDIS_PORT', '6379')}/0"
)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL') or _default_celery_broker
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND') or _default_celery_redis
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
# Глобальный потолок (страховка). Реальные лимиты задаются по воркерам через
# CLI (--time-limit / --soft-time-limit) в docker-compose, т.к. тяжёлым
# Selenium-задачам нужно больше времени, чем лёгким HTTP.
CELERY_TASK_TIME_LIMIT = int(os.getenv('CELERY_TASK_TIME_LIMIT', '1800'))
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_DNS_CATEGORY_PAUSE_SECONDS = int(os.getenv('CELERY_DNS_CATEGORY_PAUSE_SECONDS', '180'))


CELERY_TASK_ACKS_LATE = True
# False — критично для парсинга на VPS. При acks_late задача подтверждается ПОСЛЕ
# выполнения; если воркер умирает (OOM-kill SIGKILL на тяжёлом Selenium), то:
#   True  → RabbitMQ переотправляет ту же задачу → она снова падает по OOM →
#           бесконечный poison-loop (наблюдали: один «ядовитый» парсинг молотил
#           машину по кругу каждые ~90с, 177GB block I/O).
#   False → убитая задача помечается failed и НЕ переотправляется. Потерять один
#           парсинг не страшно: beat пере-планирует каждые 6ч, ручной запуск повторим.
CELERY_TASK_REJECT_ON_WORKER_LOST = False

# --- Защита памяти воркеров на VPS ---
# Перезапуск дочернего процесса после N задач освобождает память, которую
# Chrome/Selenium и sentence-transformers не всегда отдают обратно ОС.
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.getenv('CELERY_WORKER_MAX_TASKS_PER_CHILD', '10'))
# prefetch=1: воркер забирает по одной тяжёлой задаче за раз и не держит в
# памяти очередь «про запас» — критично при concurrency=1 на парсинге.
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', '1'))

# --- Разделение очередей: тяжёлые (Chrome) / лёгкие (HTTP) / прочее ---
# Тяжёлые парсеры (Selenium + Chrome, ~300-500 MB RAM каждый) изолируем в
# parsing_heavy и крутим воркером с concurrency=1, чтобы не словить OOM.
# Лёгкие HTTP-парсеры (WB, Regard) и быстрые задачи идут отдельно и могут
# выполняться параллельно без риска для памяти.
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_ROUTES = {
    'apps.prices.tasks.task_parse_category': {'queue': 'parsing_heavy'},        # DNS
    'apps.prices.tasks.task_parse_citilink_category': {'queue': 'parsing_heavy'},
    'apps.prices.tasks.task_parse_ozon_category': {'queue': 'parsing_heavy'},
    'apps.prices.tasks.task_parse_mvideo_category': {'queue': 'parsing_heavy'},  # Chrome+WAF
    'apps.prices.tasks.task_parse_wb_category': {'queue': 'parsing_light'},      # HTTP
    'apps.prices.tasks.task_parse_regard_category': {'queue': 'parsing_light'},  # HTTP
}


MERGE_AUDIT_RETENTION_DAYS = int(os.getenv('MERGE_AUDIT_RETENTION_DAYS', '90'))
MERGE_AUDIT_PURGE_BATCH = int(os.getenv('MERGE_AUDIT_PURGE_BATCH', '5000'))


PARSE_RUN_STUCK_TIMEOUT_MINUTES = int(os.getenv('PARSE_RUN_STUCK_TIMEOUT_MINUTES', '30'))

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

PARSE_DELAY_MIN = float(os.getenv('PARSE_DELAY_MIN', '1.0'))
PARSE_DELAY_MAX = float(os.getenv('PARSE_DELAY_MAX', '3.0'))
PARSE_MAX_RETRIES = int(os.getenv('PARSE_MAX_RETRIES', '3'))
PROXY_LIST = [p.strip() for p in os.getenv('PROXY_LIST', '').split(',') if p.strip()]
if os.getenv('CHROME_HEADLESS', '').strip() != '':
    CHROME_HEADLESS = os.getenv('CHROME_HEADLESS', '1') == '1'
else:
    CHROME_HEADLESS = sys.platform != 'win32'
_chrome_ver_env = os.getenv('CHROME_VERSION_MAIN', '').strip()
CHROME_VERSION_MAIN = int(_chrome_ver_env) if _chrome_ver_env.isdigit() else None


CHROME_START_MINIMIZED = os.getenv('CHROME_START_MINIMIZED', '1') == '1'


CHROME_STARTUP_TIMEOUT = int(os.getenv('CHROME_STARTUP_TIMEOUT', '90'))
DNS_CATALOG_ELEMENT_WAIT = int(os.getenv('DNS_CATALOG_ELEMENT_WAIT', '60'))
DNS_PAGE_LOAD_TIMEOUT = int(os.getenv('DNS_PAGE_LOAD_TIMEOUT', '120'))
DNS_CATALOG_SCROLL_MAX_ROUNDS = int(os.getenv('DNS_CATALOG_SCROLL_MAX_ROUNDS', '60'))
DNS_CATALOG_SCROLL_STABLE = int(os.getenv('DNS_CATALOG_SCROLL_STABLE', '5'))
DNS_CATALOG_SCROLL_MIN_ROUNDS = int(os.getenv('DNS_CATALOG_SCROLL_MIN_ROUNDS', '8'))
DNS_CATALOG_SCROLL_PAUSE_MIN = float(os.getenv('DNS_CATALOG_SCROLL_PAUSE_MIN', '2.0'))
DNS_CATALOG_SCROLL_PAUSE_MAX = float(os.getenv('DNS_CATALOG_SCROLL_PAUSE_MAX', '4.0'))
DNS_CATALOG_SCROLL_PAUSE_SHORT_MIN = float(os.getenv('DNS_CATALOG_SCROLL_PAUSE_SHORT_MIN', '1.2'))
DNS_CATALOG_SCROLL_PAUSE_SHORT_MAX = float(os.getenv('DNS_CATALOG_SCROLL_PAUSE_SHORT_MAX', '2.4'))
DNS_CATALOG_SCROLL_PAUSE_MORE_MIN = float(os.getenv('DNS_CATALOG_SCROLL_PAUSE_MORE_MIN', '2.5'))
DNS_CATALOG_SCROLL_PAUSE_MORE_MAX = float(os.getenv('DNS_CATALOG_SCROLL_PAUSE_MORE_MAX', '4.5'))
DNS_CATALOG_SCROLL_SENTINEL_SELECTOR = os.getenv(
    'DNS_CATALOG_SCROLL_SENTINEL_SELECTOR',
    '.spoiler-text-description.spoiler-text-description_layer',
).strip()
DNS_SELENIUM_HTTP_TIMEOUT = int(os.getenv('DNS_SELENIUM_HTTP_TIMEOUT', '300'))
DNS_SYNC_CATEGORY_COOLDOWN_MIN = float(os.getenv('DNS_SYNC_CATEGORY_COOLDOWN_MIN', '45'))
DNS_SYNC_CATEGORY_COOLDOWN_MAX = float(os.getenv('DNS_SYNC_CATEGORY_COOLDOWN_MAX', '120'))

DNS_USER_DATA_DIR = os.getenv(
    'DNS_USER_DATA_DIR',
    str(BASE_DIR / 'var' / 'chrome_profiles' / 'dns'),
)

# Анти-детект слой для Qrator (маскировка автоматизации/Xvfb через CDP).
DNS_STEALTH = os.getenv('DNS_STEALTH', 'true').lower() in ('1', 'true', 'yes')

# JSON с расшифрованными cookies dns-shop.ru из реального браузера
# (см. scripts/export_dns_cookies.py). Парсер инжектит их через CDP до навигации,
# чтобы пройти Qrator с готовой clearance-сессией. Пусто/нет файла — пропускаем.
DNS_COOKIES_FILE = os.getenv(
    'DNS_COOKIES_FILE',
    str(BASE_DIR / 'var' / 'chrome_profiles' / 'dns_cookies.json'),
)


CITILINK_CATALOG_ELEMENT_WAIT = int(os.getenv('CITILINK_CATALOG_ELEMENT_WAIT', '45'))
CITILINK_PAGE_LOAD_TIMEOUT = int(os.getenv('CITILINK_PAGE_LOAD_TIMEOUT', '120'))
CITILINK_MAX_PAGES = int(os.getenv('CITILINK_MAX_PAGES', '80'))

CITILINK_CITY_CODE = os.getenv('CITILINK_CITY_CODE', '').strip()


if os.getenv('CITILINK_HEADLESS', '').strip() != '':
    CITILINK_HEADLESS = os.getenv('CITILINK_HEADLESS', '0') == '1'
else:
    CITILINK_HEADLESS = False


CITILINK_USER_DATA_DIR = os.getenv(
    'CITILINK_USER_DATA_DIR',
    str(BASE_DIR / 'var' / 'chrome_profiles' / 'citilink'),
)


# === Wildberries парсер ===
# В отличие от DNS/Citilink (Selenium), WB парсер использует публичные HTTP API.
# Это в 10-20 раз быстрее, не требует Chrome и почти не блокируется.

# Регион доставки (влияет на цену!). -1257786 = Москва (по умолчанию).
# Другие dest: -337422 = СПб, -123585 = Екатеринбург, и т.д.
WB_DEST_ID = int(os.getenv('WB_DEST_ID', '-1257786'))
WB_DEST_NAME = os.getenv('WB_DEST_NAME', 'Москва')

# Максимальное количество страниц на категорию (WB разрешает до 100).
# 30 страниц × 100 товаров/стр = 3000 топовых товаров на категорию.
WB_MAX_PAGES = int(os.getenv('WB_MAX_PAGES', '30'))

# Throttling — не более N запросов в секунду (защита от 429).
# 1.0 безопаснее для WB (мы наблюдали 429 при 2.0+ rps).
WB_RATE_LIMIT_RPS = float(os.getenv('WB_RATE_LIMIT_RPS', '1.0'))

# Таймауты и ретраи для HTTP запросов
WB_REQUEST_TIMEOUT = int(os.getenv('WB_REQUEST_TIMEOUT', '15'))
WB_MAX_RETRIES = int(os.getenv('WB_MAX_RETRIES', '3'))

# Сортировка товаров в каталоге: popular | priceup | pricedown | rate | newly
WB_SORT_ORDER = os.getenv('WB_SORT_ORDER', 'popular')

# Прокси — если WB_PROXY_LIST пустой, используется общий PROXY_LIST.
WB_PROXY_LIST = (
    [p.strip() for p in os.getenv('WB_PROXY_LIST', '').split(',') if p.strip()]
    or PROXY_LIST
)

# Кеш для дерева категорий (на сколько секунд)
WB_CATEGORIES_CACHE_TTL = int(os.getenv('WB_CATEGORIES_CACHE_TTL', '86400'))  # 24 часа


OZON_PAGE_LOAD_TIMEOUT = int(os.getenv('OZON_PAGE_LOAD_TIMEOUT', '120'))
OZON_SCROLL_MAX_ROUNDS = int(os.getenv('OZON_SCROLL_MAX_ROUNDS', '50'))
OZON_SCROLL_MIN_ROUNDS = int(os.getenv('OZON_SCROLL_MIN_ROUNDS', '15'))
OZON_SCROLL_PAUSE_MIN = float(os.getenv('OZON_SCROLL_PAUSE_MIN', '1.2'))
OZON_SCROLL_PAUSE_MAX = float(os.getenv('OZON_SCROLL_PAUSE_MAX', '2.8'))
OZON_SCROLL_STABILITY_THRESHOLD = int(os.getenv('OZON_SCROLL_STABILITY_THRESHOLD', '12'))
OZON_PAGINATION_MAX_PAGES = int(os.getenv('OZON_PAGINATION_MAX_PAGES', '8'))

OZON_COOKIE_FILE = os.getenv('OZON_COOKIE_FILE', '').strip()


if os.getenv('OZON_HEADLESS', '').strip() != '':
    OZON_HEADLESS = os.getenv('OZON_HEADLESS', '0') == '1'
else:
    OZON_HEADLESS = False


OZON_USER_DATA_DIR = os.getenv(
    'OZON_USER_DATA_DIR',
    str(BASE_DIR / 'var' / 'chrome_profiles' / 'ozon'),
)


DEDUP_V2 = os.getenv('DEDUP_V2', '1') == '1'


DEDUP_SHADOW = os.getenv('DEDUP_SHADOW', '0') == '1'


DEDUP_AUTO_MERGE_THRESHOLD = float(os.getenv('DEDUP_AUTO_MERGE_THRESHOLD', '0.85'))
DEDUP_REVIEW_THRESHOLD = float(os.getenv('DEDUP_REVIEW_THRESHOLD', '0.65'))

DEDUP_REMATCH_ON_UPDATE = os.getenv('DEDUP_REMATCH_ON_UPDATE', '1') == '1'
DEDUP_REMATCH_COOLDOWN_HOURS = int(os.getenv('DEDUP_REMATCH_COOLDOWN_HOURS', '24'))

DEDUP_CROSS_SOURCE_SPECS_ENABLED = os.getenv('DEDUP_CROSS_SOURCE_SPECS_ENABLED', '1') == '1'
DEDUP_CROSS_SOURCE_SPECS_MIN_MATCHED = int(os.getenv('DEDUP_CROSS_SOURCE_SPECS_MIN_MATCHED', '2'))

# Blocking v2: расширенный candidate-pool только для REVIEW/SHADOW контуров.
# Живой AUTO-путь не расширяем, пока нет golden-set и стабильных метрик.
DEDUP_BLOCKING_V2_ENABLED = os.getenv('DEDUP_BLOCKING_V2_ENABLED', '0') == '1'


DEDUP_EMBEDDING_ENABLED = os.getenv('DEDUP_EMBEDDING_ENABLED', '1') == '1'
DEDUP_EMBEDDING_MATCH_ENABLED = os.getenv('DEDUP_EMBEDDING_MATCH_ENABLED', '1') == '1'
DEDUP_HF_HUB_TIMEOUT = int(os.getenv('DEDUP_HF_HUB_TIMEOUT', '120'))
DEDUP_EMBEDDING_LOCAL_FILES_ONLY = os.getenv('DEDUP_EMBEDDING_LOCAL_FILES_ONLY', '0') == '1'
DEDUP_EMBEDDING_MODEL = os.getenv(
    'DEDUP_EMBEDDING_MODEL',
    'intfloat/multilingual-e5-base',
)

DEDUP_EMBEDDING_DIM = int(os.getenv('DEDUP_EMBEDDING_DIM', '768'))
DEDUP_EMBEDDING_AUTO_THRESHOLD = float(os.getenv('DEDUP_EMBEDDING_AUTO_THRESHOLD', '0.86'))
DEDUP_EMBEDDING_REVIEW_THRESHOLD = float(os.getenv('DEDUP_EMBEDDING_REVIEW_THRESHOLD', '0.75'))

TIMESCALE_ENABLED = os.getenv('TIMESCALE_ENABLED', '1') == '1'
TIMESCALE_RETENTION_DAYS = int(os.getenv('TIMESCALE_RETENTION_DAYS', '365'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'apps.prices.parsers': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
# База Gemini API. По умолчанию — прямой Google. На сервере, где Google недоступен
# из РФ, сюда прописывается Cloudflare AI Gateway (провайдер google-ai-studio),
# чтобы запрос к Google уходил с нероссийского IP Cloudflare.
GEMINI_BASE_URL = os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com')
AI_COMPARE_CACHE_TTL = int(os.getenv('AI_COMPARE_CACHE_TTL', '86400'))


# === Подписки / уведомления ===
# Cooldown между повторными уведомлениями по одной подписке (часы). Пока цена
# держится ниже целевой, не спамим каждый прогон проверки.
SUBSCRIPTION_NOTIFY_COOLDOWN_HOURS = int(os.getenv('SUBSCRIPTION_NOTIFY_COOLDOWN_HOURS', '24'))


# === Email (SMTP + верификация + уведомления) ===
# В dev EMAIL_BACKEND=console → письма печатаются в stdout, SMTP не нужен.
# В проде задать EMAIL_HOST/PORT/USER/PASSWORD (Gmail, Yandex, Mailgun, etc.)
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG
    else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', '0') == '1'
# Жёсткий таймаут на SMTP — иначе медленный/висящий сервер блокирует
# синхронный воркхэндлер (отправка идёт прямо в запросе регистрации).
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '10'))
DEFAULT_FROM_EMAIL = os.getenv('EMAIL_FROM', 'Scout <noreply@example.com>')
# Базовый URL сайта — подставляется в ссылки письма (без слеша на конце).
SITE_URL = os.getenv('SITE_URL', 'http://localhost').rstrip('/')


# === Telegram-дублирование уведомлений ===
# Бот не умеет писать по @username — нужен chat_id. Его ловим polling'ом
# getUpdates (periodic Celery-задача), когда пользователь пишет боту код привязки.
# Webhook не нужен (нет публичного HTTPS на VPS).
TELEGRAM_ENABLED = os.getenv('TELEGRAM_ENABLED', '0') == '1'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', '').strip().lstrip('@')
TELEGRAM_API_TIMEOUT = int(os.getenv('TELEGRAM_API_TIMEOUT', '15'))
# Сколько действует код привязки, прежде чем протухнет (минуты).
TELEGRAM_LINK_CODE_TTL_MINUTES = int(os.getenv('TELEGRAM_LINK_CODE_TTL_MINUTES', '15'))


# === Cookies / CSRF для прод-режима ===
# В DEBUG оставляем мягкие настройки (HTTP-разработка). В проде — Secure cookies.
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')
# Фронту (SPA) нужно читать csrftoken из cookie, поэтому HttpOnly=False.
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = not DEBUG and os.getenv('COOKIE_SECURE', '1') == '1'
CSRF_COOKIE_SECURE = not DEBUG and os.getenv('COOKIE_SECURE', '1') == '1'

# За TLS-терминатором (Caddy/nginx) Django видит HTTP. Доверяем X-Forwarded-Proto,
# чтобы request.is_secure() == True и Secure-cookies/redirect'ы работали корректно.
if os.getenv('USE_PROXY_SSL_HEADER', '1') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS: браузер запоминает "только HTTPS" на заданный срок.
# Задать SECURE_HSTS_SECONDS=31536000 после того как HTTPS точно работает.
# ВНИМАНИЕ: нельзя откатить без ожидания истечения срока — включать постепенно.
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', '0') == '1'
SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', '0') == '1'

# SSL-редирект делает хостовый nginx, а не Django — иначе будет двойной редирект.
SECURE_SSL_REDIRECT = False

# Заглушаем W008: "SSL redirect не включён". Он делается на уровне nginx-прокси,
# и включать его в Django за reverse-proxy неправильно (петля редиректов).
SILENCED_SYSTEM_CHECKS = ['security.W008']
