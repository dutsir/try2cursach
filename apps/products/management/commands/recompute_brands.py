"""Пересчёт Product.brand новым категориезависимым экстрактором.

rebuild_features только ЗАПОЛНЯЕТ пустой бренд и никогда не ИСПРАВЛЯЕТ неверный.
Эта команда чинит исторический мусор: товары, у которых брендом ошибочно записан
вендор чипа (nvidia/amd/intel) в device-категориях (видеокарты/ноутбуки/...), —
бренд там должен быть производителем платы/устройства (MSI/Asus/Palit/Lenovo).

Что делает (только улучшения, без риска затереть валидные данные):
  - old=чип-вендор в device-категории  → new (реальный производитель или пусто)
  - old=пусто                          → new (заполнение)
  - old=реальный бренд, new=другой     → НЕ трогаем (только репорт divergent)

Unique-констрейнт (category, brand, vendor_code): если исправление бренда создаёт
коллизию с уже существующим товаром (тот же vendor_code, но «правильный» бренд),
это один и тот же товар — пытаемся слить через merge_products. Если слияние
запрещено (same-source guard) — оставляем бренд как есть и считаем conflict_skipped.

Dry-run по умолчанию; реальная запись — только с --apply.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.products.dedupe.merge import can_merge, merge_products
from apps.products.dedupe.normalizer import (
    _CHIP_NOT_BRAND_CATEGORIES,
    _CHIP_VENDOR_BRANDS,
    normalize_offer,
)
from apps.products.models import MergeAuditLog, Offer, Product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Пересчитать Product.brand: исправить чип-вендорный бренд, заполнить пустой, слить вскрывшиеся дубли.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true', help='Реально записывать изменения.')
        parser.add_argument('--dry-run', action='store_true', help='По умолчанию (ничего не пишет).')
        parser.add_argument('--category', type=str, default='', help='Slug категории — ограничить область.')
        parser.add_argument('--limit', type=int, default=0, help='Ограничить число товаров (для отладки).')

    def handle(self, *args: Any, **options: Any) -> None:
        apply = bool(options.get('apply'))
        cat = (options.get('category') or '').strip()
        limit = int(options.get('limit') or 0)

        self.stdout.write(self.style.NOTICE(f'Режим: {"APPLY" if apply else "DRY-RUN"}'))
        if cat:
            self.stdout.write(self.style.NOTICE(f'Категория: {cat!r}'))

        qs = Product.objects.select_related('category').only(
            'id', 'name', 'brand', 'vendor_code', 'category_id',
        )
        if cat:
            qs = qs.filter(category__slug=cat)
        if limit:
            qs = qs[:limit]

        st: Counter[str] = Counter()
        samples: list[str] = []

        for p in qs.iterator(chunk_size=500):
            st['scanned'] += 1
            slug = ''
            if p.category_id and p.category:
                slug = (p.category.slug or '').strip().lower()

            features = normalize_offer(
                name=p.name, source='', category_id=p.category_id,
                sku=p.vendor_code or '', url='', category_slug=slug,
            )
            new_brand = (features.brand or '').strip()[:64]
            old_brand = (p.brand or '').strip()

            if new_brand == old_brand:
                continue

            old_is_chip = old_brand in _CHIP_VENDOR_BRANDS
            device_cat = slug in _CHIP_NOT_BRAND_CATEGORIES

            # Решаем, является ли изменение улучшением.
            if old_is_chip and device_cat:
                action = 'correct_chip'      # nvidia → msi  или  nvidia → '' (clear)
            elif not old_brand and new_brand:
                action = 'fill'              # '' → msi
            else:
                st['divergent'] += 1         # реальный бренд → другой: не трогаем
                continue

            if not apply:
                st[action] += 1
                if action == 'correct_chip' and len(samples) < 12:
                    samples.append(f'  [{slug}] {old_brand!r}→{new_brand!r}: {(p.name or "")[:70]}')
                continue

            self._apply_one(p, new_brand=new_brand, action=action, st=st)

        self._report(st, samples, apply=apply)

    def _apply_one(
        self, p: Product, *, new_brand: str, action: str, st: Counter[str],
    ) -> None:
        # Очистка чип-вендора в '' коллизий не создаёт (условие констрейнта
        # требует brand>''), просто записываем.
        if not new_brand:
            with transaction.atomic():
                Product.objects.filter(pk=p.pk).update(brand='')
            st[action] += 1
            st['cleared'] += 1
            return

        vendor_code = (p.vendor_code or '').strip()
        if vendor_code:
            collision = (
                Product.objects
                .filter(category_id=p.category_id, brand=new_brand, vendor_code=vendor_code)
                .exclude(pk=p.pk)
                .first()
            )
            if collision is not None:
                # Тот же товар под «правильным» брендом уже есть → сливаем.
                canon, dup = self._pick_canonical(collision, p)
                ok, reason = can_merge(canon, dup)
                if not ok:
                    st['conflict_skipped'] += 1
                    logger.info(
                        'recompute_brands: коллизия не слита pk=%s/%s reason=%s',
                        canon.pk, dup.pk, reason,
                    )
                    return
                res = merge_products(
                    canon.pk, dup.pk,
                    actor=MergeAuditLog.Actor.AUTO,
                    decision=MergeAuditLog.Decision.AUTO_MERGE,
                    signals={'rule': 'brand_correction', 'new_brand': new_brand},
                    run_id='recompute_brands',
                )
                if res.get('merged'):
                    st['merged'] += 1
                    # Если выжил dup (мы сделали его canonical) — поправим бренд.
                    if canon.pk == p.pk or canon.pk == collision.pk:
                        Product.objects.filter(pk=canon.pk).update(brand=new_brand)
                else:
                    st['conflict_skipped'] += 1
                return

        with transaction.atomic():
            Product.objects.filter(pk=p.pk).update(brand=new_brand)
        st[action] += 1

    @staticmethod
    def _pick_canonical(a: Product, b: Product) -> tuple[Product, Product]:
        na = Offer.objects.filter(product=a).count()
        nb = Offer.objects.filter(product=b).count()
        return (a, b) if na >= nb else (b, a)

    def _report(self, st: Counter[str], samples: list[str], *, apply: bool) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== ИТОГ ==='))
        self.stdout.write(f'  Просмотрено товаров:        {st["scanned"]}')
        self.stdout.write(f'  Исправлено чип-вендор:      {st["correct_chip"]}')
        self.stdout.write(f'  Заполнено пустых:           {st["fill"]}')
        self.stdout.write(f'  Очищено в пусто (clear):    {st["cleared"]}')
        self.stdout.write(f'  Слияний дублей:             {st["merged"]}')
        self.stdout.write(f'  Коллизий пропущено:         {st["conflict_skipped"]}')
        self.stdout.write(f'  Расхождений (не трогали):   {st["divergent"]}')
        if samples:
            self.stdout.write('\n  Примеры исправлений чип-вендора:')
            for s in samples:
                self.stdout.write(s)
        if not apply:
            self.stdout.write(self.style.WARNING('\n  DRY-RUN — ничего не записано. Запусти с --apply.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n  Готово.'))
