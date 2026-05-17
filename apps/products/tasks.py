from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


_REVERTED_RETENTION_DAYS = 30


def _purge_merge_audit(
    *,
    retention_days: int,
    batch_size: int,
) -> dict[str, int]:
    from .models import MergeAuditLog

    cutoff_update = timezone.now() - timedelta(days=retention_days)
    cutoff_reverted = timezone.now() - timedelta(days=_REVERTED_RETENTION_DAYS)

    total_update = _delete_in_batches(
        MergeAuditLog.objects.filter(
            decision=MergeAuditLog.Decision.UPDATE,
            created_at__lt=cutoff_update,
        ),
        batch_size=batch_size,
    )
    total_reverted = _delete_in_batches(
        MergeAuditLog.objects.filter(
            reverted=True,
            created_at__lt=cutoff_reverted,
        ).exclude(decision=MergeAuditLog.Decision.UPDATE),
        batch_size=batch_size,
    )

    return {
        'deleted_update': total_update,
        'deleted_reverted': total_reverted,
        'retention_days': retention_days,
    }


def _delete_in_batches(qs, *, batch_size: int) -> int:
    total = 0
    while True:
        ids = list(qs.values_list('pk', flat=True)[:batch_size])
        if not ids:
            break
        from .models import MergeAuditLog
        with transaction.atomic():
            deleted, _ = MergeAuditLog.objects.filter(pk__in=ids).delete()
        total += deleted

        if len(ids) < batch_size:
            break
    return total


@shared_task(bind=True)
def task_purge_merge_audit(
    self,
    retention_days: int | None = None,
    batch_size: int | None = None,
) -> dict:
    days = int(
        retention_days
        if retention_days is not None
        else getattr(settings, 'MERGE_AUDIT_RETENTION_DAYS', 90)
    )
    batch = int(
        batch_size
        if batch_size is not None
        else getattr(settings, 'MERGE_AUDIT_PURGE_BATCH', 5000)
    )
    result = _purge_merge_audit(retention_days=days, batch_size=batch)
    logger.info(
        'MergeAuditLog purge: удалено %d UPDATE-записей (>%d дн.) + '
        '%d reverted-записей (>%d дн.)',
        result['deleted_update'], days,
        result['deleted_reverted'], _REVERTED_RETENTION_DAYS,
    )
    return result


__all__ = ('task_purge_merge_audit',)
