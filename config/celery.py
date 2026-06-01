import importlib
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    _celery = importlib.import_module('celery')
    _schedules = importlib.import_module('celery.schedules')
    _kombu = importlib.import_module('kombu')
    Celery = _celery.Celery
    crontab = _schedules.crontab
    Queue = _kombu.Queue

    app = Celery('price_monitor')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    if sys.platform == 'win32':
        app.conf.worker_pool = 'solo'

    # Явно объявляем очереди, чтобы RabbitMQ создал их при старте, а воркеры
    # могли подписаться через `-Q parsing_heavy` / `-Q parsing_light,default`.
    # Роутинг задач по очередям задаётся в settings.CELERY_TASK_ROUTES.
    app.conf.task_queues = (
        Queue('default'),
        Queue('parsing_heavy'),
        Queue('parsing_light'),
    )

    app.autodiscover_tasks()

    app.conf.beat_schedule = {
        # Ежедневный парсинг всех категорий (03:00 МСК).
        # DNS-задачи попадают в parsing_heavy — они обработаются только если Chrome-воркер
        # запущен на машине с прогретым Xvfb-профилем; остальные источники (WB, Citilink,
        # M.Video) работают в parsing_light и парсятся автоматически.
        'parse-all-categories-daily': {
            'task': 'apps.prices.tasks.task_parse_all_categories',
            'schedule': crontab(minute=0, hour=3),
        },
        'check-subscriptions-hourly': {
            'task': 'apps.alerts.tasks.task_check_subscriptions',
            'schedule': crontab(minute=0),
        },
        'cleanup-stuck-parseruns-every-15m': {
            'task': 'apps.prices.tasks.task_cleanup_stuck_parseruns',
            'schedule': crontab(minute='*/15'),
        },
        'purge-merge-audit-weekly': {
            'task': 'apps.products.tasks.task_purge_merge_audit',
            'schedule': crontab(minute=0, hour=4, day_of_week=0),
        },
    }
except ImportError:
    Celery = None
    crontab = None
    app = None
