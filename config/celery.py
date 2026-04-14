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

# Расписание: парсинг часто, курсы ЦБ — раз в день, прогноз — раз в неделю (можно сменить на daily).
app.conf.beat_schedule = {
    'parse-all-categories-every-6h': {
        'task': 'apps.prices.tasks.task_parse_all_categories',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    'check-subscriptions-hourly': {
        'task': 'apps.alerts.tasks.task_check_subscriptions',
        'schedule': crontab(minute=0),
    },
    'detect-anomalies-daily': {
        'task': 'apps.analytics.tasks.task_detect_all_anomalies',
        'schedule': crontab(minute=0, hour=3),
    },
    'fetch-currency-rates-daily': {
        'task': 'apps.analytics.tasks.task_fetch_currency_rates',
        'schedule': crontab(minute=30, hour=23),
    },
    'forecast-all-weekly': {
        'task': 'apps.analytics.tasks.task_forecast_all_products',
        'schedule': crontab(minute=0, hour=4, day_of_week='sun'),
    },
    'analytics-dashboard-snapshot-weekly': {
        'task': 'apps.analytics.tasks.task_save_analytics_dashboard_snapshot',
        'schedule': crontab(minute=0, hour=6, day_of_week='sun'),
    },
}
