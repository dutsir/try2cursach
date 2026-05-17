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
        'http://localhost,http://127.0.0.1',
    ).split(',')
    if x.strip()
]

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
    'apps.analytics',
    'apps.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
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
CELERY_TASK_TIME_LIMIT = 600
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_DNS_CATEGORY_PAUSE_SECONDS = int(os.getenv('CELERY_DNS_CATEGORY_PAUSE_SECONDS', '180'))


CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True


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
DNS_SELENIUM_HTTP_TIMEOUT = int(os.getenv('DNS_SELENIUM_HTTP_TIMEOUT', '300'))
DNS_SYNC_CATEGORY_COOLDOWN_MIN = float(os.getenv('DNS_SYNC_CATEGORY_COOLDOWN_MIN', '45'))
DNS_SYNC_CATEGORY_COOLDOWN_MAX = float(os.getenv('DNS_SYNC_CATEGORY_COOLDOWN_MAX', '120'))


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


ENABLE_ADVANCED_ANALYTICS = os.getenv('ENABLE_ADVANCED_ANALYTICS', '0') == '1'


DEDUP_V2 = os.getenv('DEDUP_V2', '1') == '1'


DEDUP_SHADOW = os.getenv('DEDUP_SHADOW', '0') == '1'


DEDUP_AUTO_MERGE_THRESHOLD = float(os.getenv('DEDUP_AUTO_MERGE_THRESHOLD', '0.85'))
DEDUP_REVIEW_THRESHOLD = float(os.getenv('DEDUP_REVIEW_THRESHOLD', '0.65'))


DEDUP_CROSS_SOURCE_SPECS_ENABLED = os.getenv('DEDUP_CROSS_SOURCE_SPECS_ENABLED', '1') == '1'
DEDUP_CROSS_SOURCE_SPECS_MIN_MATCHED = int(os.getenv('DEDUP_CROSS_SOURCE_SPECS_MIN_MATCHED', '2'))


DEDUP_EMBEDDING_ENABLED = os.getenv('DEDUP_EMBEDDING_ENABLED', '1') == '1'
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
        'apps.analytics.detector': {
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
