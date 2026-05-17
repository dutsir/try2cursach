import logging

from celery import shared_task

from apps.products.models import Product

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    max_retries=2,
)
def task_detect_anomalies(self, product_id: int) -> dict:
    from .detector import run_full_detection

    anomalies = run_full_detection(product_id)
    return {
        'product_id': product_id,
        'anomalies_found': len(anomalies),
    }


@shared_task
def task_detect_all_anomalies() -> dict:
    products = Product.objects.filter(is_active=True).values_list('pk', flat=True)
    count = 0
    for pk in products:
        task_detect_anomalies.delay(product_id=pk)
        count += 1
    logger.info('Поставлено задач детекции аномалий: %d', count)
    return {'queued': count}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def task_fetch_currency_rates(self) -> dict:
    from .cbr_rates import save_rates_for_date
    created = save_rates_for_date()
    return {'created': created}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=300, max_retries=1)
def task_forecast_all_products(self) -> dict:
    from .forecasting import forecast_all

    return forecast_all()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=120, max_retries=1)
def task_save_analytics_dashboard_snapshot(self) -> dict:
    from .snapshots import save_full_dashboard_snapshot

    snap = save_full_dashboard_snapshot()
    return {'snapshot_id': snap.pk, 'kind': snap.kind, 'summary_keys': list(snap.summary.keys())}
