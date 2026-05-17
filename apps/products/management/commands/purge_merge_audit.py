from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.products.models import MergeAuditLog
from apps.products.tasks import _purge_merge_audit


class Command(BaseCommand):
    help = (
        'Удалить старые UPDATE-записи MergeAuditLog '
        '(по умолчанию старше settings.MERGE_AUDIT_RETENTION_DAYS=90 дней).'
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--retention-days', type=int, default=None,
            help='Возраст UPDATE-записей в днях (default: settings.MERGE_AUDIT_RETENTION_DAYS).',
        )
        parser.add_argument(
            '--batch-size', type=int, default=None,
            help='Размер пачки для DELETE (default: settings.MERGE_AUDIT_PURGE_BATCH).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Только посчитать, что было бы удалено, без DELETE.',
        )

    def handle(self, *args, **opts) -> None:
        days = int(opts.get('retention_days') or getattr(
            settings, 'MERGE_AUDIT_RETENTION_DAYS', 90,
        ))
        batch = int(opts.get('batch_size') or getattr(
            settings, 'MERGE_AUDIT_PURGE_BATCH', 5000,
        ))

        if opts.get('dry_run'):
            cutoff_update = timezone.now() - timedelta(days=days)
            cutoff_reverted = timezone.now() - timedelta(days=30)
            cnt_update = MergeAuditLog.objects.filter(
                decision=MergeAuditLog.Decision.UPDATE,
                created_at__lt=cutoff_update,
            ).count()
            cnt_reverted = MergeAuditLog.objects.filter(
                reverted=True, created_at__lt=cutoff_reverted,
            ).exclude(decision=MergeAuditLog.Decision.UPDATE).count()
            self.stdout.write(self.style.NOTICE(
                f'dry-run: будет удалено {cnt_update} UPDATE-записей '
                f'(>{days} дн.) + {cnt_reverted} reverted (>30 дн.).'
            ))
            return

        result = _purge_merge_audit(retention_days=days, batch_size=batch)
        self.stdout.write(self.style.SUCCESS(
            f"Удалено: UPDATE={result['deleted_update']}, "
            f"reverted={result['deleted_reverted']} "
            f"(retention={result['retention_days']} дн.)"
        ))
