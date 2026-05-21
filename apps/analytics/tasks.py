"""Celery tasks for analytics.

Раньше здесь были задачи детекции аномалий, прогнозирования цен
(ARIMA) и подтягивания курсов ЦБ — они удалены, т.к. предсказание
цен и детекция аномалий больше не входят в скоуп проекта.

Оставлена только задача сохранения снэпшотов аналитического
дашборда (best_deals / clustering / parsing_metrics / price_index /
heatmap).
"""

from celery import shared_task


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=120, max_retries=1)
def task_save_analytics_dashboard_snapshot(self) -> dict:
    from .snapshots import save_full_dashboard_snapshot

    snap = save_full_dashboard_snapshot()
    return {
        'snapshot_id': snap.pk,
        'kind': snap.kind,
        'summary_keys': list(snap.summary.keys()),
    }
