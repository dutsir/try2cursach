from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from apps.products.models import MergeAuditLog, Offer, Product


def _to_iso(dt) -> str | None:
    return dt.isoformat() if dt else None


class Command(BaseCommand):
    help = (
        'Берёт случайный canary-сэмпл свежих AUTO_MERGE для ручной проверки '
        '(live precision monitoring).'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--days', type=int, default=7, help='Окно свежести в днях.')
        parser.add_argument('--size', type=int, default=50, help='Размер canary-сэмпла.')
        parser.add_argument('--seed', type=int, default=42, help='Seed для воспроизводимости.')
        parser.add_argument(
            '--output',
            default='var/dedup_auto_canary.jsonl',
            help='Путь output JSONL.',
        )
        parser.add_argument(
            '--run-id',
            default='',
            help='Опционально ограничить конкретным run_id.',
        )
        parser.add_argument(
            '--category',
            default='',
            help='Опционально ограничить категорией финального product.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = max(1, int(options['days']))
        size = max(1, int(options['size']))
        seed = int(options['seed'])
        out = Path(options['output']).resolve()
        run_id = (options.get('run_id') or '').strip()
        category = (options.get('category') or '').strip()

        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = (
            MergeAuditLog.objects
            .filter(
                actor=MergeAuditLog.Actor.AUTO,
                decision=MergeAuditLog.Decision.AUTO_MERGE,
                created_at__gte=cutoff,
                reverted=False,
            )
            .exclude(from_product_id__isnull=True)
            .exclude(to_product_id__isnull=True)
            .select_related('offer', 'from_product__category', 'to_product__category')
            .order_by('-created_at')
        )
        if run_id:
            qs = qs.filter(run_id=run_id)
        if category:
            qs = qs.filter(to_product__category__slug=category)

        logs = list(qs[:5000])
        if not logs:
            self.stdout.write(self.style.WARNING('Свежих AUTO_MERGE не найдено под заданные фильтры.'))
            return

        rng = random.Random(seed)
        sample_rows = rng.sample(logs, min(size, len(logs)))

        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open('w', encoding='utf-8') as f:
            meta = {
                'row_type': 'meta',
                'days': days,
                'requested_size': size,
                'sampled': len(sample_rows),
                'population': len(logs),
                'cutoff': cutoff.isoformat(),
                'run_id_filter': run_id,
                'category_filter': category,
                'seed': seed,
            }
            f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            for log in sample_rows:
                offer = log.offer
                from_product = log.from_product
                to_product = log.to_product
                row = {
                    'row_type': 'auto_merge_canary',
                    'audit_log_id': log.pk,
                    'created_at': _to_iso(log.created_at),
                    'run_id': log.run_id,
                    'score': float(log.score or 0),
                    'offer_id': offer.pk if offer else None,
                    'offer_source': offer.source if offer else None,
                    'offer_url': offer.url if offer else None,
                    'offer_raw_name': offer.raw_name if offer else None,
                    'from_product_id': from_product.pk if from_product else None,
                    'from_product_name': from_product.name if from_product else None,
                    'from_product_category': (
                        from_product.category.slug if from_product and from_product.category_id else None
                    ),
                    'to_product_id': to_product.pk if to_product else None,
                    'to_product_name': to_product.name if to_product else None,
                    'to_product_category': (
                        to_product.category.slug if to_product and to_product.category_id else None
                    ),
                    'signals': log.signals or {},
                    # Ручная проверка (заполняется после ревью):
                    'manual_verdict': None,  # correct_merge | wrong_merge
                    'manual_notes': '',
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')

        self.stdout.write(self.style.SUCCESS(f'Canary sample сохранён: {out}'))
        self.stdout.write(f'Population: {len(logs)} | Sampled: {len(sample_rows)}')

