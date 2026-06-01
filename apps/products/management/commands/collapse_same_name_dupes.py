"""Схлопывание дублей-товаров с ПОБУКВЕННО идентичным именем (в т.ч. within-source).

Контекст. По [[dedup-principle]] within-source non-WB офферы штатно НЕ сливаются: разные
листинги магазина = разные офферы (цена обновляется по url/sku). Но на практике один и
тот же товар у одного источника расщепляется на НЕСКОЛЬКО мастер-Product'ов с
ОДИНАКОВЫМ именем (исторические перепарсы/relisting/смена url). Пользователь видит
«один товар — N карточек». Владелец явно решил (2026-06-01): «копии хуже, чем нарушение
принципа — сливаем».

Ключ группировки — НОРМАЛИЗОВАННОЕ ПОЛНОЕ имя (`' '.join(name.lower().split())`), а НЕ
сигнатура. Это намеренно: полное имя несёт цвет/объём/part-number, поэтому «…белый» и
«…чёрный» (разные SKU) НЕ схлопываются — только побуквенные близнецы. Сигнатурный ключ
был бы опаснее (грубая сигнатура схлопывает RAM/SSD-варианты).

На группу из ≥2 товаров: canonical = товар с бОльшим числом офферов (при равенстве —
меньший id), остальные сливаются в него через `merge_products(..., allow_same_source=True)`
— ЯВНЫЙ обход same-source guard (только здесь). Разные категории при равенстве имени
merge отклонит (category_mismatch) — это ок, логируем.

Dry-run по умолчанию; запись — только с --apply.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.products.dedupe.merge import merge_products
from apps.products.models import MergeAuditLog, Offer, Product

logger = logging.getLogger(__name__)


def _name_key(name: str) -> str:
    return ' '.join((name or '').lower().split())


class Command(BaseCommand):
    help = 'Схлопывает товары с идентичным полным именем (в т.ч. within-source).'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true', help='Применить (по умолчанию dry-run).')
        parser.add_argument('--dry-run', action='store_true', help='Только показать (по умолчанию).')
        parser.add_argument('--category', default='', help='Ограничить слагом категории.')
        parser.add_argument('--limit', type=int, default=0, help='Максимум групп (0 = без лимита).')
        parser.add_argument('--show', type=int, default=15, help='Сколько примеров напечатать.')

    def handle(self, *args: Any, **opts: Any) -> None:
        apply = bool(opts['apply'])
        cat = (opts['category'] or '').strip().lower()
        limit = int(opts['limit'])
        show = int(opts['show'])

        self.stdout.write(
            f'Режим: {"APPLY" if apply else "DRY-RUN"} | '
            f'категория={cat or "все"} | limit={limit or "∞"}',
        )

        qs = Product.objects.all()
        if cat:
            qs = qs.filter(category__slug=cat)

        # число офферов на товар — для выбора canonical (богаче карточка)
        offer_count: Counter[int] = Counter()
        for pid in Offer.objects.values_list('product_id', flat=True):
            offer_count[pid] += 1

        groups: dict[tuple[int, str], list[int]] = defaultdict(list)
        for p in qs.values('id', 'name', 'category_id'):
            groups[(p['category_id'], _name_key(p['name']))].append(p['id'])

        collisions = [(k, ids) for k, ids in groups.items() if len(ids) > 1]
        extra_cards = sum(len(ids) - 1 for _, ids in collisions)
        self.stdout.write(
            f'Групп с идентичным именем (>1 товара): {len(collisions)} | '
            f'лишних карточек: {extra_cards}',
        )

        stats: Counter[str] = Counter()
        processed = 0
        printed = 0
        for (_cat_id, key), ids in collisions:
            if limit and processed >= limit:
                break
            processed += 1
            # canonical: больше офферов, при равенстве меньший id
            canonical_id = min(ids, key=lambda i: (-offer_count[i], i))
            dups = [i for i in ids if i != canonical_id]
            if printed < show:
                printed += 1
                srcs = list(
                    Offer.objects.filter(product_id__in=ids)
                    .values_list('source', flat=True),
                )
                self.stdout.write(
                    f'  «{key[:70]}» canon=#{canonical_id} dups={dups} '
                    f'srcs={sorted(set(srcs))}',
                )
            if not apply:
                stats['products_merged'] += len(dups)
                continue
            for dup_id in dups:
                mres = merge_products(
                    canonical_id, dup_id,
                    actor=MergeAuditLog.Actor.AUTO,
                    decision=MergeAuditLog.Decision.AUTO_MERGE,
                    signals={'reason': 'same_name_collapse'},
                    run_id='collapse_same_name_dupes',
                    allow_same_source=True,
                )
                if mres.get('merged'):
                    stats['products_merged'] += 1
                else:
                    stats['merge_blocked'] += 1
                    logger.warning(
                        'collapse blocked %s<-%s: %s',
                        canonical_id, dup_id, mres.get('reason'),
                    )

        self.stdout.write('=== ГОТОВО ===')
        self.stdout.write(f'  Групп обработано:  {processed}')
        self.stdout.write(f'  Товаров слито:     {stats["products_merged"]}')
        self.stdout.write(f'  Слияний отклонено: {stats["merge_blocked"]}')
        if not apply:
            self.stdout.write(self.style.WARNING('DRY-RUN. Запусти с --apply.'))
