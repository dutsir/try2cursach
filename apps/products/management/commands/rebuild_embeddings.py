from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.products.dedupe.embedding import embedding_enabled, sync_product_embedding
from apps.products.dedupe.normalizer import normalize_offer
from apps.products.models import Offer, Product


class Command(BaseCommand):
    help = 'Пересчитать match_embedding у Product по офферам / имени.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--category', type=str, default='', help='Slug категории')
        parser.add_argument('--limit', type=int, default=0, help='Лимит Product (0 = все)')
        parser.add_argument('--force', action='store_true', help='Пересчитать даже если вектор есть')

    def handle(self, *args: Any, **options: Any) -> None:
        if not embedding_enabled():
            self.stderr.write(self.style.ERROR(
                'DEDUP_EMBEDDING_ENABLED=0 или нет sentence-transformers'
            ))
            return

        qs = Product.objects.filter(is_active=True).order_by('id')
        cat_slug = (options.get('category') or '').strip()
        if cat_slug:
            qs = qs.filter(category__slug=cat_slug)
        limit = int(options.get('limit') or 0)
        if limit > 0:
            qs = qs[:limit]
        force = bool(options.get('force'))

        updated = 0
        skipped = 0
        total = qs.count()
        self.stdout.write(f'Product к обработке: {total}')

        for product in qs.iterator(chunk_size=100):


            if product.match_embedding is not None and not force:
                skipped += 1
                continue
            offer = (
                Offer.objects
                .filter(product=product)
                .order_by('-last_seen_at')
                .first()
            )
            name = (offer.raw_name if offer else '') or product.name
            src = offer.source if offer else 'dns'
            sku = (offer.source_sku if offer else '') or product.vendor_code
            url = (offer.url if offer else '') or product.url
            features = normalize_offer(
                name=name,
                source=src,
                category_id=product.category_id,
                sku=sku,
                url=url,
            )
            if sync_product_embedding(product, features, name):
                updated += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'Готово: обновлено {updated}, пропущено {skipped}'
        ))
