from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.products.dedupe.normalizer import normalize_offer
from apps.products.models import Offer, Product
from apps.products.dedupe.embedding import sync_product_embedding
from apps.products.dedupe.features import Features

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Пересобрать normalized_features у Offer и брендиндекс/specs у Product (без merge).'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true', help='Реально записывать изменения.')
        parser.add_argument('--dry-run', action='store_true', help='Алиас по умолчанию (ничего не пишет).')
        parser.add_argument(
            '--category', type=str, default='',
            help='Slug категории — ограничить область одной категорией.',
        )
        parser.add_argument(
            '--source', type=str, default='',
            help='Источник: dns/citilink/ozon — ограничить область одним магазином.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        apply = bool(options.get('apply'))
        category_slug = (options.get('category') or '').strip()
        source = (options.get('source') or '').strip().lower()

        mode = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(self.style.NOTICE(f'Режим: {mode}'))
        if category_slug:
            self.stdout.write(self.style.NOTICE(f'Категория: {category_slug!r}'))
        if source:
            self.stdout.write(self.style.NOTICE(f'Источник: {source!r}'))

        self._rebuild_offers(apply=apply, category_slug=category_slug, source=source)
        self._rebuild_products(apply=apply, category_slug=category_slug)
        self.stdout.write(self.style.SUCCESS('Готово.'))


    def _rebuild_offers(self, *, apply: bool, category_slug: str, source: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING('\n[1/2] Offer.normalized_features'))
        qs = Offer.objects.select_related('product').only(
            'id', 'source', 'url', 'source_sku', 'vendor_code', 'raw_name',
            'normalized_features', 'mpn_extracted', 'product__name', 'product__category_id',
        )
        if category_slug:
            qs = qs.filter(product__category__slug=category_slug)
        if source:
            qs = qs.filter(source=source)

        scanned = 0
        to_update: list[Offer] = []
        sources_stats: Counter[str] = Counter()
        with_mpn = 0
        with_brand = 0
        for offer in qs.iterator(chunk_size=500):
            scanned += 1

            name = (offer.raw_name or '').strip() or (offer.product.name if offer.product_id else '')
            features = normalize_offer(
                name=name,
                source=offer.source,
                category_id=offer.product.category_id if offer.product_id else None,
                sku=offer.source_sku or offer.vendor_code or '',
                url=offer.url,
            )
            if features.model_code:
                with_mpn += 1
                sources_stats[features.model_code_source] += 1
            if features.brand:
                with_brand += 1
            offer.normalized_features = features.to_jsonable()
            offer.mpn_extracted = features.model_code[:64]
            if not offer.raw_name and name:
                offer.raw_name = name
            to_update.append(offer)
            if len(to_update) >= 500 and apply:
                with transaction.atomic():
                    Offer.objects.bulk_update(
                        to_update,
                        ['normalized_features', 'mpn_extracted', 'raw_name'],
                        batch_size=500,
                    )
                to_update.clear()

        if apply and to_update:
            with transaction.atomic():
                Offer.objects.bulk_update(
                    to_update,
                    ['normalized_features', 'mpn_extracted', 'raw_name'],
                    batch_size=500,
                )

        self.stdout.write(
            f'  Просмотрено офферов: {scanned}, с распознанным MPN: {with_mpn}, '
            f'с брендом: {with_brand}'
        )
        if sources_stats:
            self.stdout.write(f'  Источники MPN: {dict(sources_stats)}')


    def _rebuild_products(self, *, apply: bool, category_slug: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING('\n[2/2] Product.brand / specs_fingerprint / key_hash / embedding'))
        qs = Product.objects.only(
            'id', 'name', 'brand', 'vendor_code', 'specs_fingerprint',
            'key_hash', 'category_id', 'match_embedding',
        )
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        scanned = 0
        updated = 0
        skipped_brand_conflicts = 0
        embeddings_synced = 0
        for p in qs.iterator(chunk_size=500):
            scanned += 1
            features = normalize_offer(
                name=p.name,
                source='',
                category_id=p.category_id,
                sku='',
                url='',
            )
            updates: list[str] = []
            if features.brand and not (p.brand or '').strip():
                candidate_brand = features.brand[:64]


                if (p.vendor_code or '').strip():
                    conflict_exists = Product.objects.filter(
                        category_id=p.category_id,
                        brand=candidate_brand,
                        vendor_code=p.vendor_code,
                    ).exclude(pk=p.pk).exists()
                    if conflict_exists:
                        skipped_brand_conflicts += 1
                    else:
                        p.brand = candidate_brand
                        updates.append('brand')
                else:
                    p.brand = candidate_brand
                    updates.append('brand')

            current_specs: dict[str, Any] = p.specs_fingerprint or {}
            merged = dict(current_specs)
            specs_changed = False
            for k, v in (features.specs or {}).items():
                if k not in merged or merged.get(k) in (None, ''):
                    merged[k] = v
                    specs_changed = True
            if specs_changed:
                p.specs_fingerprint = merged
                updates.append('specs_fingerprint')

            new_hash = features.key_hash()
            if new_hash != (p.key_hash or ''):
                p.key_hash = new_hash
                updates.append('key_hash')

            if updates and apply:
                p.save(update_fields=updates + ['updated_at'])
                updated += 1

                if sync_product_embedding(p, features, p.name):
                    embeddings_synced += 1
            elif updates:
                updated += 1

        self.stdout.write(f'  Просмотрено товаров: {scanned}, к обновлению: {updated}')
        if skipped_brand_conflicts:
            self.stdout.write(
                f'  Пропущено brand-обновлений из-за unique-конфликта: {skipped_brand_conflicts}'
            )
        if apply:
            self.stdout.write(f'  Embeddings синхронизированы: {embeddings_synced}')
