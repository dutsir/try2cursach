"""Backfill: создаёт ProductFamily для существующих Product и привязывает их.

Сейчас поддерживаются категории SSD/HDD (см. _SSD_LIKE_SLUGS в family.py).
Для всех остальных категорий family у Product остаётся None — мы НЕ
создаём одиночные семьи 1:1, чтобы не плодить мусорные записи.

Идемпотентен: повторный запуск без --reset видит уже созданные семьи через
family_key_hash и присоединяется к ним.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.dedupe.family import derive_family_name, make_family_signature
from apps.products.models import (
    Category,
    MergeAuditLog,
    Product,
    ProductFamily,
)

logger = logging.getLogger(__name__)


DEFAULT_SLUGS = (
    'ssd-nakopiteli', 'zhestkie-diski-35', 'servernye-nakopiteli',
    'vneshnie-ssd',
    'noutbuki', 'sobrannyepk', 'monobloki', 'mikrokompyutery',
    'operativnaya-pamyat', 'servernaya-pamyat',
)


class Command(BaseCommand):
    help = (
        'Создаёт ProductFamily для существующих Product (SSD/HDD). '
        'Для категорий без поддержки вариантов family остаётся None.'
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--slugs', nargs='+', default=list(DEFAULT_SLUGS),
            help='Какие категории обработать (по умолчанию SSD/HDD).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Только отчёт, без записи в БД.',
        )
        parser.add_argument(
            '--reset', action='store_true',
            help='Перед обработкой обнулить Product.family в категории '
                 'и удалить все ProductFamily этой категории.',
        )
        parser.add_argument(
            '--run-id', default='',
            help='ID прогона для MergeAuditLog (по умолчанию backfill-<timestamp>).',
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        run_id = opts['run_id'] or f'backfill-{int(time.time())}'
        slugs: list[str] = list(opts['slugs'])
        dry = bool(opts['dry_run'])
        reset = bool(opts['reset'])

        self.stdout.write(
            f'Backfill ProductFamily: slugs={slugs} dry-run={dry} reset={reset} run_id={run_id}'
        )
        for slug in slugs:
            self._process_category(slug, dry=dry, reset=reset, run_id=run_id)

    def _process_category(
        self, slug: str, *, dry: bool, reset: bool, run_id: str,
    ) -> None:
        cat = Category.objects.filter(slug=slug).first()
        if cat is None:
            raise CommandError(f'Категория не найдена: {slug}')

        self.stdout.write(self.style.MIGRATE_HEADING(f'\n=== {slug} ==='))

        qs = Product.objects.filter(category=cat).only(
            'id', 'name', 'brand', 'vendor_code', 'specs_fingerprint',
            'family_id', 'variant_specs', 'variant_key_hash',
        )

        # Группируем по family_key — товары с одинаковой моделью.
        groups: dict[str, list[tuple[Product, dict[str, Any]]]] = defaultdict(list)
        skipped_unrecognized = 0
        total = 0
        for p in qs:
            total += 1
            sig = make_family_signature(
                name=p.name, brand=p.brand or '',
                vendor_code=p.vendor_code or '',
                specs=p.specs_fingerprint,
                category_slug=slug,
            )
            if sig is None:
                skipped_unrecognized += 1
                continue
            groups[sig['family_key']].append((p, sig))

        self.stdout.write(
            f'  товаров всего: {total}; распознано в семьи: {sum(len(v) for v in groups.values())}; '
            f'без распознанной модели (останутся family=None): {skipped_unrecognized}'
        )
        self.stdout.write(f'  будет создано/обновлено семей: {len(groups)}')

        if dry:
            self.stdout.write(self.style.WARNING('  --dry-run: ничего не записываю'))
            return

        with transaction.atomic():
            if reset:
                affected = Product.objects.filter(
                    category=cat, family__isnull=False,
                ).update(family=None, variant_specs={}, variant_key_hash='')
                deleted, _ = ProductFamily.objects.filter(category=cat).delete()
                self.stdout.write(
                    f'  reset: обнулена family у {affected} Product, удалено {deleted} ProductFamily'
                )

            created_families = 0
            attached_products = 0
            for family_key, items in groups.items():
                family = self._upsert_family(family_key, items, category=cat)
                if family is not None and family._was_created:  # type: ignore[attr-defined]
                    created_families += 1
                attached_products += self._attach_variants(family, items, run_id=run_id)

            self.stdout.write(self.style.SUCCESS(
                f'  готово: семей создано {created_families}, '
                f'Product привязано к семьям {attached_products}'
            ))

    def _upsert_family(
        self,
        family_key: str,
        items: list[tuple[Product, dict[str, Any]]],
        *,
        category: Category,
    ) -> ProductFamily:
        # Все items этой группы имеют одинаковые brand + model_code + common_specs,
        # поэтому берём метаданные из первого.
        first_product, first_sig = items[0]
        existing = ProductFamily.objects.filter(family_key_hash=family_key).first()
        if existing is not None:
            existing._was_created = False  # type: ignore[attr-defined]
            return existing
        family = ProductFamily.objects.create(
            name=derive_family_name(first_product.name) or first_product.name[:512],
            brand=first_product.brand or '',
            model_code=first_sig['model_code'][:128],
            category=category,
            common_specs=first_sig['common_specs'],
            family_key_hash=family_key,
        )
        family._was_created = True  # type: ignore[attr-defined]
        return family

    def _attach_variants(
        self,
        family: ProductFamily,
        items: list[tuple[Product, dict[str, Any]]],
        *,
        run_id: str,
    ) -> int:
        attached = 0
        for product, sig in items:
            # Проверяем, нужно ли действительно обновлять.
            if (
                product.family_id == family.id
                and product.variant_key_hash == sig['variant_key']
                and product.variant_specs == sig['variant_specs']
            ):
                continue
            product.family = family
            product.variant_specs = sig['variant_specs']
            product.variant_key_hash = sig['variant_key']
            product.save(update_fields=['family', 'variant_specs', 'variant_key_hash', 'updated_at'])
            MergeAuditLog.objects.create(
                from_product=None,
                to_product=product,
                actor=MergeAuditLog.Actor.MIGRATION,
                decision=MergeAuditLog.Decision.UPDATE,
                run_id=run_id,
                signals={
                    'kind': 'family_backfill',
                    'family_id': family.id,
                    'family_key_hash': family.family_key_hash,
                    'model_code': sig['model_code'],
                    'variant_specs': sig['variant_specs'],
                    'variant_key_hash': sig['variant_key'],
                },
            )
            attached += 1
        return attached
