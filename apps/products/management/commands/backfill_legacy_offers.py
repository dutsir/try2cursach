from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.prices.models import PriceHistory
from apps.products.models import Offer, Product

logger = logging.getLogger(__name__)

_SOURCE_URL_MARKERS: dict[str, tuple[str, ...]] = {
    'dns': ('dns-shop.ru', 'dns-shop.com'),
    'citilink': ('citilink.ru',),
    'ozon': ('ozon.ru',),
}


def _url_matches_source(url: str, source: str) -> bool:
    low = (url or '').lower()
    if not low:
        return False
    markers = _SOURCE_URL_MARKERS.get(source, ())
    return any(m in low for m in markers)


class Command(BaseCommand):
    help = (
        'Создать Offer для legacy PriceHistory без offer_id '
        '(данные парсинга до модели Offer).'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--source',
            action='append',
            dest='sources',
            choices=['dns', 'citilink', 'ozon'],
            help='Ограничить магазином (можно указать несколько раз).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только подсчитать, без записи в БД.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Максимум продуктов за прогон (0 = без лимита).',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        sources = options.get('sources') or list(_SOURCE_URL_MARKERS.keys())
        dry_run = bool(options.get('dry_run'))
        limit = int(options.get('limit') or 0)

        stats = {s: {'offers': 0, 'ph_linked': 0, 'skipped_no_url': 0} for s in sources}

        for source in sources:
            self.stdout.write(self.style.MIGRATE_HEADING(f'\n=== {source} ==='))
            has_offer = Offer.objects.filter(product_id=OuterRef('pk'), source=source)
            qs = (
                Product.objects
                .filter(price_history__source=source)
                .exclude(Exists(has_offer))
                .distinct()
                .order_by('id')
            )
            if limit:
                qs = qs[:limit]

            total = qs.count()
            self.stdout.write(f'  Кандидатов (Product с PH, без Offer): {total}')

            for product in qs.iterator(chunk_size=200):
                url = (product.url or '').strip()
                if not _url_matches_source(url, source):
                    stats[source]['skipped_no_url'] += 1
                    continue

                if dry_run:
                    stats[source]['offers'] += 1
                    ph_count = PriceHistory.objects.filter(
                        product=product, source=source, offer__isnull=True,
                    ).count()
                    stats[source]['ph_linked'] += ph_count
                    continue

                with transaction.atomic():
                    offer, created = Offer.objects.get_or_create(
                        source=source,
                        url=url[:1024],
                        defaults={
                            'product': product,
                            'vendor_code': (product.vendor_code or '')[:128],
                            'source_sku': '',
                            'raw_name': product.name,
                            'is_available': True,
                            'last_seen_at': timezone.now(),
                        },
                    )
                    if not created and offer.product_id != product.pk:
                        logger.warning(
                            'Offer %s уже привязан к product_id=%s, пропуск product_id=%s',
                            offer.pk, offer.product_id, product.pk,
                        )
                        continue

                    if created:
                        stats[source]['offers'] += 1

                    updated = PriceHistory.objects.filter(
                        product=product,
                        source=source,
                        offer__isnull=True,
                    ).update(offer=offer)
                    stats[source]['ph_linked'] += updated

        self.stdout.write(self.style.SUCCESS('\nИтог:'))
        for source, s in stats.items():
            self.stdout.write(
                f'  {source}: offers_created={s["offers"]}, '
                f'price_history_linked={s["ph_linked"]}, '
                f'skipped_no_url={s["skipped_no_url"]}'
            )
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: изменений в БД нет.'))
