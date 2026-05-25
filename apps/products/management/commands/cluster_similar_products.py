"""Кластеризует похожие Products через pgvector embedding similarity.

Использует существующие embeddings (intfloat/multilingual-e5-base, 384-dim,
HNSW индекс на Product.match_embedding). Находит пары Products одной категории
с высокой семантической близостью и сливает их.

Это работает как "облегчённый LLM" — нейросеть-encoder уже понимает что
"Видеокарта MSI RTX 4060" и "MSI GeForce RTX 4060 8GB" — это одно и то же,
даже если экстракторы regex'ом не нашли точного матча.

⚠️ ВАЖНО: команда учитывает безопасность:
  - Сливает только если cosine similarity > threshold (по умолчанию 0.92)
  - Дополнительно проверяет Dice score по названиям (>= 0.6)
  - НЕ сливает Products с разными variant_specs
  - НЕ сливает merge_locked
  - Делает в транзакции, есть --dry-run

Использование:
    # Обзор: посмотреть что будет слито
    python manage.py cluster_similar_products --dry-run --category myshi

    # Применить для одной категории с высоким порогом (только полные дубли)
    python manage.py cluster_similar_products --apply --category myshi --threshold 0.95

    # Все категории сразу (опасно! начни с dry-run)
    python manage.py cluster_similar_products --apply --threshold 0.92
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import connection, transaction

from apps.products.models import Category, Offer, Product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Кластеризует похожие Products через pgvector embedding similarity. '
        'Находит дубликаты которые regex-экстракторы пропустили.'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true', help='Применить.')
        parser.add_argument('--dry-run', action='store_true', help='Только посмотреть.')
        parser.add_argument(
            '--category', type=str, help='Slug категории (без — все).',
        )
        parser.add_argument(
            '--threshold', type=float, default=0.97,
            help='Минимальная cosine similarity для слияния (0..1). '
                 'По умолчанию 0.97 (очень строго — только дубли).',
        )
        parser.add_argument(
            '--name-similarity-threshold', type=float, default=0.85,
            help='Минимальная Dice similarity по названиям (по умолчанию 0.85). '
                 'Защита от слияния разных моделей одного бренда.',
        )
        parser.add_argument(
            '--max-pairs', type=int, default=10000,
            help='Максимум пар к обработке за один прогон.',
        )
        parser.add_argument(
            '--no-transitive', action='store_true', default=True,
            help='БЕЗ transitive closure. Сливать только пары (по умолчанию). '
                 'Защищает от каскадного слияния разных товаров.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        is_apply: bool = options.get('apply', False)
        is_dry_run: bool = not is_apply
        category_slug: str = (options.get('category') or '').strip()
        threshold: float = float(options.get('threshold', 0.92))
        name_sim_threshold: float = float(options.get('name_similarity_threshold', 0.6))
        max_pairs: int = int(options.get('max_pairs', 10000))

        self.stdout.write(self.style.NOTICE(
            f"Режим: {'DRY-RUN' if is_dry_run else 'APPLY'} | "
            f"cosine threshold: {threshold} | "
            f"name similarity: {name_sim_threshold} | "
            f"category: {category_slug or 'все'}"
        ))

        # Получаем категории к обработке
        if category_slug:
            categories = [Category.objects.get(slug=category_slug)]
        else:
            categories = list(Category.objects.filter(is_active=True))

        total_pairs = 0
        total_merged = 0
        total_moved_offers = 0

        for cat in categories:
            pairs = self._find_similar_pairs(
                category_id=cat.pk,
                threshold=threshold,
                max_pairs=max_pairs,
            )
            if not pairs:
                continue

            self.stdout.write(f"\n━━━ {cat.slug} ━━━")
            self.stdout.write(f"  Найдено похожих пар: {len(pairs)}")

            # БЕЗ transitive closure — сливаем пары независимо.
            # Каждая пара проверяется отдельно (name_similarity + variant).
            # Это защищает от каскадного слияния через transitive closure.

            if is_dry_run:
                # Показать первые 10 пар как пример
                self.stdout.write(f"  Первые 10 пар:")
                for a, b, sim in pairs[:10]:
                    pa = Product.objects.filter(pk=a).first()
                    pb = Product.objects.filter(pk=b).first()
                    if pa and pb:
                        name_sim = self._name_similarity(pa.name, pb.name)
                        marker = '✅' if name_sim >= name_sim_threshold else '⏭ '
                        self.stdout.write(
                            f"    {marker} sim={sim:.3f} name_sim={name_sim:.2f}"
                        )
                        self.stdout.write(f"       [{a}] {pa.name[:80]}")
                        self.stdout.write(f"       [{b}] {pb.name[:80]}")
                continue

            # Apply: обрабатываем каждую пару независимо
            cat_merged = 0
            cat_moved = 0
            seen_ids: set[int] = set()  # уже обработанные (избегаем повторных)
            for a, b, sim in pairs:
                if a in seen_ids or b in seen_ids:
                    continue
                stats = self._merge_pair(
                    a, b,
                    name_sim_threshold=name_sim_threshold,
                )
                if stats['products_deleted'] > 0:
                    seen_ids.add(b)  # b удалён, не трогаем
                cat_merged += stats['products_deleted']
                cat_moved += stats['offers_moved']

            total_pairs += len(pairs)
            total_merged += cat_merged
            total_moved_offers += cat_moved
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ Слито Products: {cat_merged}, перенесено offers: {cat_moved}"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\n=== ИТОГО ==="
            f"\n  Кластеров обработано: {total_pairs}"
            f"\n  Products слито:       {total_merged}"
            f"\n  Offers перенесено:    {total_moved_offers}"
        ))

    def _find_similar_pairs(
        self, *, category_id: int, threshold: float, max_pairs: int,
    ) -> list[tuple[int, int, float]]:
        """Находит пары Products одной категории с cosine similarity > threshold.

        Использует pgvector cosine distance (<=>).
        cosine_distance = 1 - cosine_similarity
        Поэтому threshold=0.92 → distance < 0.08
        """
        max_distance = 1.0 - threshold

        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p1.id, p2.id,
                    1 - (p1.match_embedding <=> p2.match_embedding) AS similarity
                FROM products_product p1
                JOIN products_product p2
                    ON p1.id < p2.id
                    AND p1.category_id = p2.category_id
                WHERE p1.category_id = %s
                  AND p1.match_embedding IS NOT NULL
                  AND p2.match_embedding IS NOT NULL
                  AND p1.is_active = TRUE
                  AND p2.is_active = TRUE
                  AND p1.merge_locked = FALSE
                  AND p2.merge_locked = FALSE
                  AND (p1.match_embedding <=> p2.match_embedding) < %s
                ORDER BY similarity DESC
                LIMIT %s
                """,
                [category_id, max_distance, max_pairs],
            )
            return [(row[0], row[1], float(row[2])) for row in cur.fetchall()]

    @staticmethod
    def _cluster_pairs(pairs: list[tuple[int, int, float]]) -> list[set[int]]:
        """Union-Find: группирует пары в связанные компоненты.

        Если A↔B и B↔C — все трое в одной группе.
        """
        parent: dict[int, int] = {}

        def find(x: int) -> int:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent.get(x, x), parent.get(x, x))
                x = parent.get(x, x)
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for a, b, _ in pairs:
            parent.setdefault(a, a)
            parent.setdefault(b, b)
            union(a, b)

        groups: dict[int, set[int]] = {}
        for node in parent:
            root = find(node)
            groups.setdefault(root, set()).add(node)

        return [g for g in groups.values() if len(g) >= 2]

    @transaction.atomic
    def _merge_pair(
        self, id_a: int, id_b: int, *, name_sim_threshold: float,
    ) -> dict[str, int]:
        """Сливает 2 Products (только если проходят защиты).

        Canonical = тот у кого больше offers (или старше при равенстве).
        """
        from django.db.models import Count

        # Получаем offer counts
        products_info = list(
            Product.objects.filter(pk__in=[id_a, id_b])
            .annotate(off_count=Count('offers'))
            .values('id', 'off_count')
        )
        if len(products_info) != 2:
            return {'products_deleted': 0, 'offers_moved': 0}

        # Sortируем: canonical первый (больше offers, потом старше)
        products_info.sort(key=lambda p: (-p['off_count'], p['id']))
        canonical_id, dup_id = products_info[0]['id'], products_info[1]['id']

        # Лочим
        locked = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=[canonical_id, dup_id])
        }
        if canonical_id not in locked or dup_id not in locked:
            return {'products_deleted': 0, 'offers_moved': 0}

        canonical = locked[canonical_id]
        dup = locked[dup_id]

        # Защита: variant_specs
        cv = (canonical.specs_fingerprint or {}).get('variant_key', '')
        dv = (dup.specs_fingerprint or {}).get('variant_key', '')
        if cv and dv and cv != dv:
            return {'products_deleted': 0, 'offers_moved': 0}

        # Защита: name similarity
        sim = self._name_similarity(canonical.name, dup.name)
        if sim < name_sim_threshold:
            return {'products_deleted': 0, 'offers_moved': 0}

        # Слияние
        moved = Offer.objects.filter(product=dup).update(product=canonical)
        try:
            from apps.prices.models import PriceHistory
            PriceHistory.objects.filter(product=dup).update(product=canonical)
        except Exception:
            pass
        dup.delete()
        return {'products_deleted': 1, 'offers_moved': moved}

    @transaction.atomic
    def _merge_cluster(
        self, ids: list[int], *, name_sim_threshold: float,
    ) -> dict[str, int]:
        """Сливает все Products одного кластера в canonical (с защитой)."""
        from django.db.models import Count

        if len(ids) < 2:
            return {'products_deleted': 0, 'offers_moved': 0}

        # Сначала offer counts (для выбора canonical), потом lock
        counts = list(
            Product.objects.filter(pk__in=ids)
            .annotate(off_count=Count('offers'))
            .order_by('-off_count', 'created_at')
            .values('id', 'off_count')
        )
        sorted_ids = [c['id'] for c in counts]

        # Лочим
        locked = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=sorted_ids)
        }
        products = [locked[i] for i in sorted_ids if i in locked]
        if len(products) < 2:
            return {'products_deleted': 0, 'offers_moved': 0}

        canonical = products[0]
        stats = {'products_deleted': 0, 'offers_moved': 0}

        for dup in products[1:]:
            # Защита 1: variant_specs
            cv = (canonical.specs_fingerprint or {}).get('variant_key', '')
            dv = (dup.specs_fingerprint or {}).get('variant_key', '')
            if cv and dv and cv != dv:
                continue

            # Защита 2: name similarity
            sim = self._name_similarity(canonical.name, dup.name)
            if sim < name_sim_threshold:
                continue

            # Слияние
            moved = Offer.objects.filter(product=dup).update(product=canonical)
            stats['offers_moved'] += moved
            try:
                from apps.prices.models import PriceHistory
                PriceHistory.objects.filter(product=dup).update(product=canonical)
            except Exception:
                pass
            dup.delete()
            stats['products_deleted'] += 1

        return stats

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        """Dice score по токенам."""
        import re

        def tokenize(s: str) -> set[str]:
            return set(re.findall(r'[a-zа-яё0-9]{2,}', (s or '').lower()))

        ta, tb = tokenize(a), tokenize(b)
        if not ta or not tb:
            return 0.0
        return (2 * len(ta & tb)) / (len(ta) + len(tb))
