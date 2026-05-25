"""Сливает Products-дубликаты с одинаковым (key_hash, category) в canonical.

🚨 ВНИМАНИЕ: ИСПОЛЬЗОВАТЬ С ОСТОРОЖНОСТЬЮ!

ПРОБЛЕМА: Команда полагается на key_hash (brand + model_code).
Если нормализатор НЕ извлекает model_code для категории (например для
материнских плат, процессоров, видеокарт), то key_hash = только brand,
и команда сольёт РАЗНЫЕ модели в одну.

Пример катастрофы (выявлено в проде):
  207 материнок Gigabyte имеют один key_hash (т.к. model_code не извлекается).
  Если их слить — получим ОДИН "товар Gigabyte" с 207 разными моделями.

КОГДА БЕЗОПАСНО ИСПОЛЬЗОВАТЬ:
  ✅ Для категорий где model_code извлекается надёжно (RAM, SSD, HDD,
     ноутбуки) — там VARIANT_SPEC_KEYS_BY_CATEGORY.
  ❌ Для materinskie-platy, processory, videokarty, monitory — model_code
     ещё не извлекается, НЕ применять!

РЕШЕНИЕ ПЕРЕД ИСПОЛЬЗОВАНИЕМ:
  1. Сначала улучшить нормализатор (apps/products/dedupe/family.py)
     чтобы model_code извлекался для нужной категории.
  2. Запустить rebuild_features --apply
  3. Только потом merge_duplicate_products

⚠️ ВАЖНО: команда учитывает безопасность:
  - НЕ сливает Products с пустым key_hash (нет brand/model_code)
  - НЕ сливает если у Products разные variant_specs (это варианты, не дубли)
  - НЕ сливает merge_locked Products
  - Делает все в транзакции, есть --dry-run
  - ВСЕГДА начинай с --dry-run и проверяй ЧТО именно сливается!

Использование:
    # Только посмотреть что будет слито
    python manage.py merge_duplicate_products --dry-run

    # Применить для одной категории
    python manage.py merge_duplicate_products --apply --category videokarty

    # Применить везде (осторожно!)
    python manage.py merge_duplicate_products --apply
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import Count

from apps.products.models import Category, Offer, Product

logger = logging.getLogger(__name__)


# Хэши которые означают "пусто" или почти пусто (без brand/model_code).
# Это хэш от строк типа '||' или '|||' (только разделители).
# Такие Products нельзя сливать — это разные товары с не извлечённой моделью.
EMPTY_KEY_HASH_PREFIXES = (
    '3eb4162',  # hash от '|' (пустые brand+model_code)
    'da39a3e',  # hash от пустой строки
    'd0763ed',  # hash от '|'
    'a7c6f1a',  # ещё один частый "пустой" хэш
)


def _is_empty_hash(key_hash: str) -> bool:
    """Проверяет, является ли key_hash 'пустым' (хэш от brand+model_code='')."""
    if not key_hash:
        return True
    return any(key_hash.startswith(prefix) for prefix in EMPTY_KEY_HASH_PREFIXES)


class Command(BaseCommand):
    help = (
        'Сливает Products-дубликаты с одинаковым (key_hash, category). '
        'Все Offer\'ы и PriceHistory переключаются на canonical Product.'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Применить изменения. По умолчанию dry-run.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать что будет слито (по умолчанию).',
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Slug категории (без него — все категории)',
        )
        parser.add_argument(
            '--min-group-size',
            type=int,
            default=2,
            help='Минимальный размер группы дублей (по умолчанию 2)',
        )
        parser.add_argument(
            '--include-empty-hash',
            action='store_true',
            help='ОПАСНО! Включать Products с пустым key_hash. '
                 'НЕ ИСПОЛЬЗОВАТЬ если не уверен — может слить разные товары!',
        )
        parser.add_argument(
            '--name-similarity-threshold',
            type=float,
            default=0.7,
            help='Минимальное Dice-similarity названий для слияния (0..1). '
                 'По умолчанию 0.7. Защищает от слияния разных моделей.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        is_apply: bool = options.get('apply', False)
        is_dry_run: bool = not is_apply
        category_slug: str = (options.get('category') or '').strip()
        min_group: int = options.get('min_group_size', 2)
        include_empty: bool = options.get('include_empty_hash', False)
        self.name_sim_threshold: float = float(options.get('name_similarity_threshold', 0.7))

        self.stdout.write(self.style.NOTICE(
            f"Режим: {'DRY-RUN' if is_dry_run else 'APPLY'} | "
            f"min_group_size={min_group} | "
            f"category={'все' if not category_slug else category_slug} | "
            f"include_empty={include_empty}"
        ))

        # 1. Найти дубли
        qs = Product.objects.exclude(key_hash='')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        groups = (
            qs.values('key_hash', 'category_id', 'category__slug')
            .annotate(c=Count('id'))
            .filter(c__gte=min_group)
            .order_by('-c')
        )

        # 2. Отфильтровать пустые хэши
        valid_groups = []
        skipped_empty = 0
        for g in groups:
            if not include_empty and _is_empty_hash(g['key_hash']):
                skipped_empty += 1
                continue
            valid_groups.append(g)

        total_groups = len(valid_groups)
        total_extra = sum(g['c'] - 1 for g in valid_groups)

        self.stdout.write(self.style.NOTICE(
            f"\nНайдено групп дублей: {total_groups} (потенциально слить: {total_extra} Products)"
        ))
        if skipped_empty:
            self.stdout.write(
                f"  (пропущено {skipped_empty} групп с 'пустым' key_hash — "
                f"add --include-empty-hash чтобы включить)"
            )

        if total_groups == 0:
            self.stdout.write(self.style.WARNING('Нет групп для слияния.'))
            return

        # 3. Топ-20 для preview
        self.stdout.write('\nТоп-20 групп для слияния:')
        for g in valid_groups[:20]:
            self.stdout.write(
                f"  [{g['category__slug']:30}] key={g['key_hash'][:12]} → "
                f"{g['c']} Products"
            )

        if is_dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDRY-RUN: ничего не изменилось. Запусти с --apply.'
            ))
            return

        # 4. Применяем
        self.stdout.write('\n=== APPLY ===')
        merged_groups = 0
        merged_products = 0
        moved_offers = 0
        errors = 0

        for g in valid_groups:
            try:
                stats = self._merge_group(
                    key_hash=g['key_hash'],
                    category_id=g['category_id'],
                )
                merged_groups += 1
                merged_products += stats['products_deleted']
                moved_offers += stats['offers_moved']
                if merged_groups % 50 == 0:
                    self.stdout.write(
                        f"  [{merged_groups}/{total_groups}] "
                        f"продуктов слито: {merged_products}, "
                        f"офферов перенесено: {moved_offers}"
                    )
            except Exception as exc:
                errors += 1
                logger.exception(
                    'Ошибка слияния группы key_hash=%s cat=%s: %s',
                    g['key_hash'][:12], g['category__slug'], exc,
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n=== ГОТОВО ==='
            f'\n  Групп обработано:   {merged_groups}/{total_groups}'
            f'\n  Products удалено:   {merged_products}'
            f'\n  Offer перенесено:   {moved_offers}'
            f'\n  Ошибок:             {errors}'
        ))

    @transaction.atomic
    def _merge_group(
        self,
        *,
        key_hash: str,
        category_id: int,
    ) -> dict[str, int]:
        """Сливает все Products одной группы (key_hash + category) в один canonical.

        Canonical Product: тот, у которого больше всего офферов (если равно — старше).

        Возвращает stats: {products_deleted, offers_moved, history_moved}.
        """
        # Сначала получаем offer counts (нельзя GROUP BY + FOR UPDATE одновременно)
        products_with_counts = list(
            Product.objects
            .filter(key_hash=key_hash, category_id=category_id, is_active=True)
            .filter(merge_locked=False)
            .annotate(off_count=Count('offers'))
            .order_by('-off_count', 'created_at')
            .values('id', 'off_count')
        )
        if len(products_with_counts) < 2:
            return {'products_deleted': 0, 'offers_moved': 0}

        # Затем блокируем сами Products (без GROUP BY)
        product_ids = [p['id'] for p in products_with_counts]
        products_locked = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=product_ids)
        }
        # Сортируем в том же порядке (canonical первый)
        products = [products_locked[p['id']] for p in products_with_counts if p['id'] in products_locked]
        if len(products) < 2:
            return {'products_deleted': 0, 'offers_moved': 0}

        canonical = products[0]
        duplicates = products[1:]

        stats = {'products_deleted': 0, 'offers_moved': 0}

        for dup in duplicates:
            # Защита 1: variant_key должны совпадать (или быть пустыми)
            canonical_variant = (canonical.specs_fingerprint or {}).get('variant_key', '')
            dup_variant = (dup.specs_fingerprint or {}).get('variant_key', '')
            if canonical_variant and dup_variant and canonical_variant != dup_variant:
                logger.debug(
                    'Пропускаем merge product %d → %d: разные variant_key',
                    dup.pk, canonical.pk,
                )
                continue

            # Защита 2: similarity названий (Dice score по токенам).
            # Защищает от слияния "Gigabyte B760M" и "Gigabyte B850M" если
            # они получили одинаковый key_hash из-за плохого нормализатора.
            similarity = self._name_similarity(canonical.name, dup.name)
            threshold = getattr(self, 'name_sim_threshold', 0.7)
            if similarity < threshold:
                logger.debug(
                    'Пропускаем merge product %d → %d: low similarity %.2f < %.2f. '
                    'Names: %r vs %r',
                    dup.pk, canonical.pk, similarity, threshold,
                    canonical.name[:60], dup.name[:60],
                )
                continue

            # Переключаем все офферы на canonical
            offers_count = Offer.objects.filter(product=dup).update(product=canonical)
            stats['offers_moved'] += offers_count

            # PriceHistory тоже переключаем (если есть)
            try:
                from apps.prices.models import PriceHistory
                PriceHistory.objects.filter(product=dup).update(product=canonical)
            except Exception:
                logger.debug('PriceHistory не обновился для product %d', dup.pk)

            # Удаляем дубликат
            dup.delete()
            stats['products_deleted'] += 1

        return stats

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        """Dice score по токенам названий. 1.0 = идентичны, 0.0 = ничего общего."""
        import re

        def tokenize(s: str) -> set[str]:
            s = (s or '').lower()
            # Убираем пунктуацию, оставляем только слова длиной 2+
            tokens = re.findall(r'[a-zа-яё0-9]{2,}', s)
            return set(tokens)

        ta = tokenize(a)
        tb = tokenize(b)
        if not ta or not tb:
            return 0.0
        inter = len(ta & tb)
        total = len(ta) + len(tb)
        return (2 * inter) / total if total else 0.0
