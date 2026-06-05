"""Межисточниковое связывание: сводит один реальный товар, продающийся в разных
магазинах (DNS/Citilink/M.Video/WB/...), в ОДИН мастер-Product с офферами из
разных источников — чтобы на фронте было видно сравнение цен по площадкам.

СТРАТЕГИЯ (согласована с владельцем):
  • AUTO  — одинаковый brand + ТОЧНО совпадающая «сигнатура модели» (см.
    dedupe/cross_source.py) + непротиворечивые specs + НЕпересекающиеся источники
    → сливаем сразу (merge_products).
  • REVIEW — высокая, но не точная похожесть сигнатур (Dice ≥ порога) → кладём в
    очередь ручного подтверждения (MatchReview), НЕ сливаем автоматически. Это
    ловит варианты вроде EAGLE/AERO, 8GB/16GB, которые НЕ должны слиться молча.

Сливаются только товары РАЗНЫХ источников (source-наборы не пересекаются) — это
сохраняет инвариант «≤1 оффер на non-WB источник в мастере» (см. [[dedup-principle]]).
Слияния двух WB-карточек тут не делаем — это забота внутри-WB дедупликации.

Использование:
    python manage.py link_cross_source --dry-run                 # все категории
    python manage.py link_cross_source --apply --category videokarty
    python manage.py link_cross_source --apply --no-review       # только AUTO
    python manage.py link_cross_source --apply --threshold 0.85
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Count

from apps.products.dedupe.audit import enqueue_review
from apps.products.dedupe.blocking_v2 import (
    collect_blocking_v2_pairs,
    load_blocking_v2_products,
)
from apps.products.dedupe.cross_source import (
    is_discriminating,
    model_signature,
    model_tokens,
    signature_dice,
    specs_conflict,
)
from apps.products.dedupe.embedding import cosine_similarity
from apps.products.dedupe.merge import merge_products
from apps.products.models import Category, Offer, Product

logger = logging.getLogger(__name__)


class _P:
    """Лёгкое представление Product для бакетинга."""
    __slots__ = ('pk', 'brand', 'name', 'specs', 'sources', 'offers', 'sig', 'emb')

    def __init__(self, pk: int, brand: str, name: str, specs: dict,
                 sources: frozenset[str], offers: int,
                 emb: list[float] | None = None) -> None:
        self.pk = pk
        self.brand = brand
        self.name = name
        self.specs = specs or {}
        self.sources = sources
        self.offers = offers
        self.sig = model_signature(name, brand)
        self.emb = emb


class Command(BaseCommand):
    help = (
        'Связывает один товар из разных магазинов в один мастер-Product '
        '(AUTO для точных совпадений сигнатуры, REVIEW для похожих).'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true',
                            help='Применить. По умолчанию dry-run.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Только показать (по умолчанию).')
        parser.add_argument('--category', type=str, default='',
                            help='Slug категории (без него — все).')
        parser.add_argument('--threshold', type=float, default=0.80,
                            help='Порог Dice сигнатур для REVIEW (по умолчанию 0.80).')
        parser.add_argument('--cosine-threshold', type=float, default=0.90,
                            help='Порог embedding-cosine для пометки high_confidence в '
                                 'review (по умолчанию 0.90). Cosine — сигнал уверенности, '
                                 'НЕ расширяет recall (см. комментарий в _build_plans).')
        parser.add_argument('--no-review', action='store_true',
                            help='Не создавать MatchReview (только AUTO-слияния).')
        parser.add_argument('--limit', type=int, default=0,
                            help='Максимум AUTO-слияний (0 = без лимита).')
        parser.add_argument(
            '--blocking-v2',
            action='store_true',
            help=(
                'Использовать multi-pass blocking v2 ТОЛЬКО для REVIEW/экспорта. '
                'AUTO-слияния остаются прежними.'
            ),
        )
        parser.add_argument(
            '--blocking-v2-max-pairs',
            type=int,
            default=300000,
            help='Ограничение числа candidate-пар для blocking v2 (по умолчанию 300000).',
        )
        parser.add_argument(
            '--blocking-v2-max-bucket',
            type=int,
            default=120,
            help='Максимальный размер trigram-бакета в blocking v2 (по умолчанию 120).',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        is_apply: bool = options.get('apply', False)
        category_slug: str = (options.get('category') or '').strip()
        threshold: float = float(options.get('threshold', 0.80))
        cosine_threshold: float = float(options.get('cosine_threshold', 0.90))
        no_review: bool = options.get('no_review', False)
        limit: int = options.get('limit', 0) or 0
        use_blocking_v2: bool = bool(
            options.get('blocking_v2')
            or getattr(settings, 'DEDUP_BLOCKING_V2_ENABLED', False)
        )
        blocking_v2_max_pairs: int = int(options.get('blocking_v2_max_pairs') or 300000)
        blocking_v2_max_bucket: int = int(options.get('blocking_v2_max_bucket') or 120)

        self.stdout.write(self.style.NOTICE(
            f"Режим: {'APPLY' if is_apply else 'DRY-RUN'} | "
            f"категория={category_slug or 'все'} | "
            f"dice≥{threshold} | cosine≥{cosine_threshold} | "
            f"review={'off' if no_review else 'on'} | limit={limit or '∞'} | "
            f"blocking_v2={'on' if use_blocking_v2 else 'off'}"
        ))

        cats = self._resolve_categories(category_slug)
        run_id = f'cross_source_{int(time.time())}'

        total_auto = total_review = total_merged_products = errors = 0
        review_samples: list[str] = []

        for cat in cats:
            auto_plan, review_plan = self._build_plans(
                cat=cat,
                threshold=threshold,
                no_review=no_review,
                use_blocking_v2=use_blocking_v2,
                blocking_v2_max_pairs=blocking_v2_max_pairs,
                blocking_v2_max_bucket=blocking_v2_max_bucket,
            )
            if not auto_plan and not review_plan:
                continue
            self.stdout.write(self.style.NOTICE(
                f"\n[{cat.slug}] AUTO-слияний: {sum(len(d) for _, d in auto_plan)} "
                f"в {len(auto_plan)} группах | REVIEW-пар: {len(review_plan)}"
            ))
            for canon, dups in auto_plan[:5]:
                self.stdout.write(
                    f"  AUTO canon={canon.pk} ({','.join(sorted(canon.sources))}) "
                    f"+ {len(dups)} → {sorted(canon.sig)[:5]}"
                )
            for canon, dup, dice, cos, passes in review_plan[:5]:
                review_samples.append(
                    f"  REVIEW dice={dice:.2f} cos={cos:.2f} "
                    f"passes={','.join(passes[:3])} "
                    f"{canon.pk}({','.join(sorted(canon.sources))})"
                    f" ~ {dup.pk}({','.join(sorted(dup.sources))}) | "
                    f"{canon.name[:38]!r} ~ {dup.name[:38]!r}"
                )

            if not is_apply:
                total_auto += sum(len(d) for _, d in auto_plan)
                total_review += len(review_plan)
                continue

            for canon, dups in auto_plan:
                for dup in dups:
                    if limit and total_merged_products >= limit:
                        break
                    try:
                        res = merge_products(
                            canon.pk, dup.pk,
                            score=1.0,
                            signals={'cross_source': True, 'sig': sorted(canon.sig)},
                            run_id=run_id,
                        )
                        if res.get('merged'):
                            total_merged_products += 1
                            total_auto += 1
                        else:
                            logger.warning('merge skipped %s→%s: %s',
                                           dup.pk, canon.pk, res.get('reason'))
                    except Exception as exc:
                        errors += 1
                        logger.exception('merge fail %s→%s: %s', dup.pk, canon.pk, exc)

            if not no_review:
                total_review += self._apply_reviews(review_plan, cosine_threshold)

        self.stdout.write('\n=== ПРИМЕРЫ REVIEW ===')
        for s in review_samples[:15]:
            self.stdout.write(s)

        if not is_apply:
            self.stdout.write(self.style.WARNING(
                f'\nDRY-RUN: AUTO-слияний бы={total_auto}, REVIEW-пар бы={total_review}. '
                f'Запусти с --apply.'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'\n=== ГОТОВО ==='
            f'\n  AUTO слияний:       {total_auto}'
            f'\n  Products удалено:   {total_merged_products}'
            f'\n  REVIEW создано:     {total_review}'
            f'\n  Ошибок:             {errors}'
        ))

    def _resolve_categories(self, slug: str) -> list[Category]:
        qs = Category.objects.all()
        if slug:
            qs = qs.filter(slug=slug)
        return list(qs)

    def _load_products(self, cat: Category) -> list[_P]:
        rows = (
            Product.objects.filter(category=cat, is_active=True, merge_locked=False)
            .annotate(n_off=Count('offers'))
            .filter(n_off__gt=0)
            .values('id', 'brand', 'name', 'specs_fingerprint', 'n_off',
                    'match_embedding')
        )
        if not rows:
            return []
        ids = [r['id'] for r in rows]
        src_map: dict[int, set[str]] = defaultdict(set)
        for pid, src in (
            Offer.objects.filter(product_id__in=ids)
            .values_list('product_id', 'source')
        ):
            if src:
                src_map[pid].add(src.lower())
        out: list[_P] = []
        for r in rows:
            emb = r['match_embedding']
            out.append(_P(
                pk=r['id'], brand=r['brand'] or '', name=r['name'] or '',
                specs=r['specs_fingerprint'], sources=frozenset(src_map[r['id']]),
                offers=r['n_off'],
                emb=[float(x) for x in emb] if emb is not None else None,
            ))
        return out

    def _build_plans(
        self,
        *,
        cat: Category,
        threshold: float,
        no_review: bool,
        use_blocking_v2: bool,
        blocking_v2_max_pairs: int,
        blocking_v2_max_bucket: int,
    ) -> tuple[list[tuple[_P, list[_P]]], list[tuple[_P, _P, float, float, list[str]]]]:
        all_prods = self._load_products(cat)
        prods = [p for p in all_prods if is_discriminating(p.sig)]

        # бакеты по бренду
        by_brand: dict[str, list[_P]] = defaultdict(list)
        for p in prods:
            by_brand[p.brand.strip().lower()].append(p)

        auto_plan: list[tuple[_P, list[_P]]] = []
        review_plan: list[tuple[_P, _P, float, float, list[str]]] = []
        consumed: set[int] = set()

        for brand, group in by_brand.items():
            if len(group) < 2:
                continue

            # --- AUTO: точное совпадение сигнатуры ---
            by_sig: dict[frozenset[str], list[_P]] = defaultdict(list)
            for p in group:
                by_sig[p.sig].append(p)

            for sig, members in by_sig.items():
                if len(members) < 2:
                    continue
                # canonical = больше офферов, тай-брейк меньший pk (детерминизм)
                members.sort(key=lambda x: (-x.offers, x.pk))
                canon = members[0]
                canon_sources = set(canon.sources)
                dups: list[_P] = []
                for cand in members[1:]:
                    # только РАЗНЫЕ источники (cross-source) + без конфликта specs
                    if cand.sources & canon_sources:
                        continue
                    if specs_conflict(canon.specs, cand.specs):
                        continue
                    dups.append(cand)
                    canon_sources |= cand.sources
                if dups:
                    auto_plan.append((canon, dups))
                    consumed.add(canon.pk)
                    consumed.update(d.pk for d in dups)

            # --- REVIEW: похожие, но не точные сигнатуры ---
            if no_review:
                continue
            if use_blocking_v2:
                continue
            rest = [p for p in group if p.pk not in consumed]
            n = len(rest)
            for i in range(n):
                a = rest[i]
                for j in range(i + 1, n):
                    b = rest[j]
                    if a.sources & b.sources:
                        continue
                    if a.sig == b.sig:
                        continue
                    # Идентичность модели (чип+память) должна совпадать: разный
                    # чип (rtx5050 vs rtx5060) или память (8gb vs 16gb) — это
                    # РАЗНЫЕ товары, не кандидаты на review. Этот гард обязателен
                    # и для embedding-ветки — он не даёт cosine склеить разные чипы.
                    if model_tokens(a.sig) != model_tokens(b.sig):
                        continue
                    if specs_conflict(a.specs, b.specs):
                        continue
                    dice = signature_dice(a.sig, b.sig)
                    # Гейт — лексический (Dice по сигнатуре, где токен производителя
                    # присутствует → защита от кросс-бренда). Embedding-cosine НЕ
                    # расширяет recall: на видеокартах brand='nvidia' (чип, не AIB),
                    # поэтому cosine считает все «RTX 5060 8GB» похожими (~0.96) и
                    # затащил бы в очередь MSI↔ZOTAC↔Palit — мусор. Cosine идёт лишь
                    # как сигнал уверенности (сортировка/приоритет в ручной очереди).
                    if dice >= threshold:
                        cos = cosine_similarity(a.emb, b.emb) if (a.emb and b.emb) else 0.0
                        # canonical — у кого больше офферов
                        canon, dup = (a, b) if a.offers >= b.offers else (b, a)
                        review_plan.append((canon, dup, dice, cos, ['brand_signature_dice']))

        if not no_review and use_blocking_v2:
            review_plan = self._build_review_plan_v2(
                cat=cat,
                all_prods=all_prods,
                consumed=consumed,
                threshold=threshold,
                max_pairs=blocking_v2_max_pairs,
                max_bucket_size=blocking_v2_max_bucket,
            )

        return auto_plan, review_plan

    def _apply_reviews(
        self, review_plan: list[tuple[_P, _P, float, float, list[str]]],
        cosine_threshold: float,
    ) -> int:
        created = 0
        for canon, dup, dice, cos, passes in review_plan:
            canon_obj = Product.objects.filter(pk=canon.pk).first()
            if canon_obj is None:
                continue
            for offer in Offer.objects.filter(product_id=dup.pk):
                obj = enqueue_review(
                    offer=offer, suggested=canon_obj,
                    score=dice,
                    signals={'cross_source': True, 'dice': round(dice, 3),
                             'cosine': round(cos, 3),
                             'blocking_passes': passes,
                             'high_confidence': cos >= cosine_threshold,
                             'dup_product': dup.pk},
                )
                if obj is not None:
                    created += 1
        return created

    def _build_review_plan_v2(
        self,
        *,
        cat: Category,
        all_prods: list[_P],
        consumed: set[int],
        threshold: float,
        max_pairs: int,
        max_bucket_size: int,
    ) -> list[tuple[_P, _P, float, float, list[str]]]:
        by_id: dict[int, _P] = {p.pk: p for p in all_prods}
        products_v2 = load_blocking_v2_products(category_slug=cat.slug)
        pair_passes, _stats = collect_blocking_v2_pairs(
            products_v2,
            max_pairs=max_pairs,
            max_bucket_size=max_bucket_size,
        )

        out: list[tuple[_P, _P, float, float, list[str]]] = []
        for (a_id, b_id), passes in pair_passes.items():
            if a_id in consumed or b_id in consumed:
                continue
            a = by_id.get(a_id)
            b = by_id.get(b_id)
            if a is None or b is None:
                continue
            # Для non-MPN пассов держим защиту по identity-токенам:
            # разный чип/объём памяти не должен даже идти в review.
            if 'category_mpn_exact' not in passes and model_tokens(a.sig) != model_tokens(b.sig):
                continue
            dice = signature_dice(a.sig, b.sig)
            if dice < threshold and 'category_mpn_exact' not in passes:
                continue
            cos = cosine_similarity(a.emb, b.emb) if (a.emb and b.emb) else 0.0
            canon, dup = (a, b) if a.offers >= b.offers else (b, a)
            out.append((canon, dup, dice, cos, sorted(passes)))

        out.sort(key=lambda x: (x[2], x[3], x[0].offers), reverse=True)
        return out
