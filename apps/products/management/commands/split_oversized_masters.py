"""Разделяет мастер-Products, в которые ошибочно слиплись разные товары
одного источника (over-merge), на отдельные Products.

КОНТЕКСТ: исторически find_master был source-agnostic и не имел гарда «не более
одного оффера на источник в одном мастере». Для источников вне WB (dns, citilink,
mvideo, regard, ozon) товары в категории уникальны по url/sku, поэтому несколько
офферов ОДНОГО источника на одном Product — это всегда ошибочная склейка
(напр. 92 разные мыши DEXP под одним Product). Гард в matcher.find_master уже
не даёт новым склейкам появляться; эта команда чинит уже накопленные данные.

ЛОГИКА:
  - Берём (product, source) группы где офферов одного non-WB источника > 1.
  - Один оффер-«якорь» остаётся на исходном мастере (с наибольшей историей цен,
    тай-брейк — самый старый). Остальные офферы выносятся каждый в свой Product.
  - PriceHistory строки конкретного оффера переезжают на его новый Product.
  - WB не трогаем — там внутренняя дедупликация легитимна.

Использование:
    # посмотреть масштаб (ничего не меняет)
    python manage.py split_oversized_masters --dry-run
    python manage.py split_oversized_masters --apply --source mvideo
    python manage.py split_oversized_masters --apply --category videokarty
    python manage.py split_oversized_masters --apply        # все non-WB
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import Count

from django.utils import timezone

from apps.products.dedupe.matcher import WITHIN_SOURCE_DEDUP_SOURCES
from apps.products.dedupe.normalizer import normalize_offer
from apps.products.dedupe.services import _features_to_product, _make_unique_slug
from apps.products.dedupe.embedding import pick_display_name, sync_product_embedding
from apps.products.dedupe.family_service import attach_product_to_family
from apps.products.dedupe.features import Features
from apps.products.models import Category, Offer, Product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Разделяет over-merged мастера (несколько офферов одного non-WB '
        'источника на одном Product) на отдельные Products.'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true',
                            help='Применить изменения. По умолчанию dry-run.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Только показать что будет сделано (по умолчанию).')
        parser.add_argument('--source', type=str, default='',
                            help='Источник(и) через запятую (dns,citilink,mvideo,...). '
                                 'По умолчанию — все кроме WB.')
        parser.add_argument('--category', type=str, default='',
                            help='Slug категории (без него — все).')
        parser.add_argument('--limit', type=int, default=0,
                            help='Максимум (product,source)-групп для обработки (0 = без лимита).')

    def handle(self, *args: Any, **options: Any) -> None:
        is_apply: bool = options.get('apply', False)
        category_slug: str = (options.get('category') or '').strip()
        limit: int = options.get('limit', 0) or 0

        sources = self._resolve_sources(options.get('source', ''))
        self.stdout.write(self.style.NOTICE(
            f"Режим: {'APPLY' if is_apply else 'DRY-RUN'} | "
            f"источники={','.join(sorted(sources))} | "
            f"категория={'все' if not category_slug else category_slug} | "
            f"limit={limit or '∞'}"
        ))

        groups = self._find_oversized_groups(sources, category_slug)
        if limit:
            groups = groups[:limit]

        total_groups = len(groups)
        total_extra = sum(g['n'] - 1 for g in groups)
        self.stdout.write(self.style.NOTICE(
            f"\nНайдено over-merged групп (product,source): {total_groups}; "
            f"офферов к выносу: {total_extra}"
        ))
        if total_groups == 0:
            self.stdout.write(self.style.WARNING('Нечего разделять.'))
            return

        self.stdout.write('\nТоп-15 групп:')
        for g in groups[:15]:
            p = Product.objects.filter(pk=g['product_id']).first()
            pname = (p.name[:55] if p else '?')
            self.stdout.write(
                f"  product={g['product_id']} src={g['source']:8} "
                f"offers={g['n']:3} | {pname!r}"
            )

        if not is_apply:
            self.stdout.write(self.style.WARNING(
                '\nDRY-RUN: ничего не изменилось. Запусти с --apply.'
            ))
            return

        self.stdout.write('\n=== APPLY ===')
        processed = moved = new_products = errors = 0
        for i, g in enumerate(groups, 1):
            try:
                stats = self._split_group(
                    product_id=g['product_id'], source=g['source'],
                )
                processed += 1
                moved += stats['offers_moved']
                new_products += stats['products_created']
                if i % 100 == 0:
                    self.stdout.write(
                        f"  [{i}/{total_groups}] вынесено офферов={moved}, "
                        f"создано Products={new_products}"
                    )
            except Exception as exc:
                errors += 1
                logger.exception(
                    'Ошибка split product=%s src=%s: %s',
                    g['product_id'], g['source'], exc,
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n=== ГОТОВО ==='
            f'\n  Групп обработано:   {processed}/{total_groups}'
            f'\n  Офферов вынесено:   {moved}'
            f'\n  Products создано:   {new_products}'
            f'\n  Ошибок:             {errors}'
        ))

    def _resolve_sources(self, raw: str) -> set[str]:
        all_non_wb = {
            s for s in Offer.objects.values_list('source', flat=True).distinct()
            if s and s.lower() not in WITHIN_SOURCE_DEDUP_SOURCES
        }
        if not raw.strip():
            return all_non_wb
        requested = {s.strip().lower() for s in raw.split(',') if s.strip()}
        bad = {s for s in requested if s in WITHIN_SOURCE_DEDUP_SOURCES}
        if bad:
            self.stdout.write(self.style.WARNING(
                f"Источники {bad} имеют внутреннюю дедупликацию — пропускаю."
            ))
        return requested - WITHIN_SOURCE_DEDUP_SOURCES

    def _find_oversized_groups(
        self, sources: set[str], category_slug: str,
    ) -> list[dict[str, Any]]:
        qs = Offer.objects.filter(source__in=sources)
        if category_slug:
            qs = qs.filter(product__category__slug=category_slug)
        rows = (
            qs.values('product_id', 'source')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
            .order_by('-n')
        )
        return list(rows)

    def _create_standalone_product(
        self, features: Features, *, offer: Offer, category: Category,
    ) -> Product:
        """Создаёт отдельный Product для оффера, НЕ переиспользуя по brand+MPN.

        vendor_code оставляем пустым, чтобы условный unique-ключ
        (category, brand, vendor_code) не схлопывал разные карты с одинаковым
        «фейковым» MPN (напр. RTX5060TI у разных моделей GIGABYTE).
        """
        name = offer.raw_name or features.brand or 'product'
        display = pick_display_name(name) or name
        product = Product.objects.create(
            name=display[:512],
            slug=_make_unique_slug(name, offer.source_sku or ''),
            category=category,
            vendor_code='',
            brand=(features.brand or '')[:64],
            specs_fingerprint=features.specs,
            key_hash=features.key_hash,
            url=offer.url or '',
            image_url=(offer.image_url or '')[:1024],
            is_active=True,
            last_parsed_at=timezone.now(),
        )
        sync_product_embedding(product, features, name)
        return product

    @transaction.atomic
    def _split_group(self, *, product_id: int, source: str) -> dict[str, int]:
        master = (
            Product.objects.select_for_update().filter(pk=product_id).first()
        )
        if master is None:
            return {'offers_moved': 0, 'products_created': 0}

        offers = list(
            Offer.objects
            .filter(product_id=product_id, source=source)
            .annotate(ph=Count('price_history'))
            .order_by('-ph', 'created_at')
        )
        if len(offers) < 2:
            return {'offers_moved': 0, 'products_created': 0}

        category = master.category
        # offers[0] — якорь, остаётся на master. Остальные выносим.
        to_split = offers[1:]
        stats = {'offers_moved': 0, 'products_created': 0}

        from apps.prices.models import PriceHistory

        for offer in to_split:
            features = normalize_offer(
                name=offer.raw_name or master.name,
                source=source,
                category_id=category.pk,
                sku=offer.source_sku or '',
                url=offer.url or '',
                mpn_hint=offer.mpn_extracted or '',
            )
            new_product, created = _features_to_product(
                features,
                name=offer.raw_name or master.name,
                image_url=offer.image_url or '',
                fallback_url=offer.url or '',
                category=category,
            )
            # _features_to_product переиспользует Product по (brand, vendor_code).
            # Для категорий с «фейковым» MPN (видеокарты/матплаты: vendor_code =
            # чип, общий для разных моделей) это вернёт мастер с уже имеющимся
            # оффером источника → пересоздаст ту же склейку. В таком случае
            # создаём отдельный Product без vendor_code (условный unique-ключ
            # (category, brand, vendor_code) на пустой vendor_code не действует).
            if new_product.pk == master.pk or Offer.objects.filter(
                product=new_product, source=source,
            ).exists():
                new_product = self._create_standalone_product(
                    features, offer=offer, category=category,
                )
                created = True

            offer.product = new_product
            offer.save(update_fields=['product', 'updated_at'])
            PriceHistory.objects.filter(offer=offer).update(product=new_product)

            attach_product_to_family(
                new_product,
                category_slug=category.slug,
                name=offer.raw_name or new_product.name,
                brand=features.brand,
                vendor_code=features.model_code,
                specs=features.specs,
            )

            stats['offers_moved'] += 1
            if created:
                stats['products_created'] += 1

        return stats
