from __future__ import annotations

from collections import Counter
from datetime import timedelta
from random import sample
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Count
from django.utils import timezone

from apps.products.models import MatchReview, MergeAuditLog, Product


class Command(BaseCommand):
    help = 'KPI/аудит дедупликации: coverage, review queue, merge volatility, rejects.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--days', type=int, default=7,
            help='Окно в днях для merge_error_rate/hard_reject_rate (по умолчанию 7).',
        )
        parser.add_argument(
            '--sample-size', type=int, default=50,
            help='Размер сэмпла auto-merge для ручной проверки precision.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = max(1, int(options.get('days') or 7))
        sample_size = max(1, int(options.get('sample_size') or 50))
        cutoff = timezone.now() - timedelta(days=days)

        total_products = Product.objects.count()
        multi_source_products = Product.objects.annotate(
            src_count=Count('offers__source', distinct=True),
        ).filter(src_count__gte=2).count()
        coverage = (multi_source_products / total_products) if total_products else 0.0

        review_queue_depth = MatchReview.objects.filter(status=MatchReview.Status.PENDING).count()
        silent_orphans = Product.objects.filter(offers__isnull=True).count()

        offers_changed = MergeAuditLog.objects.filter(
            created_at__gte=cutoff,
            decision=MergeAuditLog.Decision.AUTO_MERGE,
        ).exclude(from_product_id__isnull=True).exclude(to_product_id__isnull=True)
        changes_by_offer = Counter(offers_changed.values_list('offer_id', flat=True))
        offers_changed_more_than_once = sum(
            1 for _offer_id, cnt in changes_by_offer.items() if _offer_id and cnt > 1
        )
        merge_error_rate = (
            offers_changed_more_than_once / len(changes_by_offer)
            if changes_by_offer else 0.0
        )

        scored_pairs = MergeAuditLog.objects.filter(created_at__gte=cutoff).exclude(
            decision=MergeAuditLog.Decision.UPDATE,
        ).count()
        hard_reject_rate = (
            MergeAuditLog.objects.filter(
                created_at__gte=cutoff,
                signals__rejected__isnull=False,
            ).count() / scored_pairs
            if scored_pairs else 0.0
        )

        auto_merges = list(
            MergeAuditLog.objects.filter(
                decision=MergeAuditLog.Decision.AUTO_MERGE,
            ).order_by('-created_at').values_list('id', flat=True)[:500]
        )
        sampled_ids = sample(auto_merges, min(sample_size, len(auto_merges))) if auto_merges else []

        self.stdout.write('Dedup KPI report')
        self.stdout.write(f'  window_days: {days}')
        self.stdout.write(f'  total_products: {total_products}')
        self.stdout.write(
            f'  cross_source_coverage: {coverage:.2%} '
            f'({multi_source_products}/{total_products or 1})'
        )
        self.stdout.write(f'  merge_error_rate: {merge_error_rate:.2%}')
        self.stdout.write(f'  review_queue_depth: {review_queue_depth}')
        self.stdout.write(f'  silent_orphans: {silent_orphans}')
        self.stdout.write(f'  hard_reject_rate: {hard_reject_rate:.2%}')
        self.stdout.write(
            '  auto_merge_precision: manual_sample_pending '
            f'({len(sampled_ids)} rows, ids={sampled_ids[:10]})'
        )

        if merge_error_rate > 0.02:
            self.stdout.write(self.style.WARNING('ALERT: merge_error_rate > 2%'))
        if review_queue_depth > 200:
            self.stdout.write(self.style.WARNING('ALERT: review_queue_depth > 200'))
        if silent_orphans > 0:
            self.stdout.write(self.style.WARNING('ALERT: silent_orphans > 0'))
