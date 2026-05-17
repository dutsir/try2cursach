import importlib
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

_celery = importlib.import_module('celery')
_schedules = importlib.import_module('celery.schedules')

Celery = _celery.Celery
crontab = _schedules.crontab
app = Celery('price_monitor')
app.config_from_object('django.conf:settings', namespace='CELERY')
if sys.platform == 'win32':
    app.conf.worker_pool = 'solo'
app.autodiscover_tasks()

_enable_analytics = os.getenv('ENABLE_ADVANCED_ANALYTICS', '0') == '1'

app.conf.beat_schedule = {
    'parse-all-categories-every-6h': {
        'task': 'apps.prices.tasks.task_parse_all_categories',
        'schedule': crontab(minute=0, hour='*/6'),
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

if _enable_analytics:
    app.conf.beat_schedule['detect-anomalies-daily'] = {
        'task': 'apps.analytics.tasks.task_detect_all_anomalies',
        'schedule': crontab(minute=0, hour=3),
    }
