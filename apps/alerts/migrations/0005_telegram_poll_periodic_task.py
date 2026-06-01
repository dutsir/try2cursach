from django.db import migrations


def create_poll_task(apps, schema_editor):
    """Регистрирует periodic-задачу опроса Telegram (раз в 30 сек).

    Создаётся ВЫКЛЮЧЕННОЙ: включите её в админке django-celery-beat после того,
    как зададите TELEGRAM_BOT_TOKEN и TELEGRAM_ENABLED=1. Так задача не молотит
    getUpdates вхолостую, пока интеграция не настроена.
    """
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    schedule, _ = IntervalSchedule.objects.get_or_create(every=30, period='seconds')
    PeriodicTask.objects.get_or_create(
        name='telegram-poll-updates',
        defaults={
            'interval': schedule,
            'task': 'apps.alerts.tasks.task_poll_telegram_updates',
            'enabled': False,
        },
    )


def remove_poll_task(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name='telegram-poll-updates').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '0004_notification_is_read_notification_product_and_more'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_poll_task, remove_poll_task),
    ]
