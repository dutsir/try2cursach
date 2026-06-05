from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Count

from apps.products.dedupe.blocking_v2 import (
    BlockingV2Product,
    collect_blocking_v2_pairs,
    load_blocking_v2_products,
)
from apps.products.dedupe.cross_source import model_signature, model_tokens, signature_dice
from apps.products.dedupe.embedding import cosine_similarity
from apps.products.models import MatchReview, Offer, Product


def _pair_key(a: int, b: int) -> str:
    left, right = (a, b) if a < b else (b, a)
    return f'{left}:{right}'


def _vec_to_list(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(x) for x in value]
    except Exception:
        return None


# Порог «подозрительного over-merge»: товар, чьи офферы рассыпаются на >= N
# несовместимых model_tokens-групп — это почти всегда мусорный мердж, а не
# обычное расхождение в названии. Такие кейсы лечатся отдельно (split), и в
# обычный divergent-поток их тащить нельзя — они его перекашивают.
_DIVERGENCE_OVERMERGE_GROUPS = 6


def _classify_divergence(toksets: list[frozenset[str]]) -> str:
    """Классифицирует расхождение model_tokens внутри одного товара.

    nested_subset    — все группы образуют цепочку по ⊆ (один оффер просто
                       дописал спеку: {16gb} vs {16gb, 3200}). Это НЕ реальное
                       расхождение — тот же товар, шум в названии. Отбрасываем.
    disjoint_conflict — есть пара групп без общих токенов и нет общего ядра:
                       офферы описывают разные модели/ёмкости. Сильный сигнал
                       мис-мерджа.
    overlap_partial  — группы делят часть токенов, но различаются: серая зона,
                       нужен человек.
    """
    n = len(toksets)
    if n <= 1:
        return 'nested_subset'
    all_comparable = True
    has_disjoint_pair = False
    for i in range(n):
        for j in range(i + 1, n):
            a, b = toksets[i], toksets[j]
            if a <= b or b <= a:
                continue
            all_comparable = False
            if not (a & b):
                has_disjoint_pair = True
    if all_comparable:
        return 'nested_subset'
    shared_core = set(toksets[0])
    for s in toksets[1:]:
        shared_core &= s
    if has_disjoint_pair and not shared_core:
        return 'disjoint_conflict'
    return 'overlap_partial'


class Command(BaseCommand):
    help = (
        'Экспортирует единый triage-пул для дедупликации: pending-review, '
        'blocking-v2 candidate pairs и multi-offer divergent.'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--output',
            default='var/dedup_triage.jsonl',
            help='Путь JSONL-экспорта triage-пула.',
        )
        parser.add_argument(
            '--golden-template-output',
            default='',
            help='Опционально: путь для шаблона golden-set (JSONL) по pair-строкам.',
        )
        parser.add_argument(
            '--category',
            default='',
            help='Ограничить экспорт конкретной категорией (slug).',
        )
        parser.add_argument(
            '--include-review',
            action='store_true',
            help='Включить pending MatchReview пары.',
        )
        parser.add_argument(
            '--include-blocking-v2',
            action='store_true',
            help='Включить candidate-пары из blocking v2.',
        )
        parser.add_argument(
            '--include-divergent',
            action='store_true',
            help='Включить multi-offer divergent товары.',
        )
        parser.add_argument(
            '--blocking-v2-max-pairs',
            type=int,
            default=300000,
            help='Лимит candidate-пар из blocking v2.',
        )
        parser.add_argument(
            '--blocking-v2-max-bucket',
            type=int,
            default=120,
            help='Максимальный размер trigram-бакета в blocking v2.',
        )
        parser.add_argument(
            '--divergent-limit',
            type=int,
            default=0,
            help='Лимит divergent строк (0 = без лимита).',
        )
        parser.add_argument(
            '--divergent-keep-nested',
            action='store_true',
            help=(
                'Не отбрасывать nested_subset divergent (цепочка ⊆ — один '
                'оффер просто дописал спеку). По умолчанию они исключаются как '
                'ложное расхождение.'
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        out_path = Path(options['output']).resolve()
        golden_path_raw = (options.get('golden_template_output') or '').strip()
        golden_path = Path(golden_path_raw).resolve() if golden_path_raw else None
        category_slug = (options.get('category') or '').strip()

        include_review = bool(options.get('include_review'))
        include_blocking_v2 = bool(options.get('include_blocking_v2'))
        include_divergent = bool(options.get('include_divergent'))
        # Если флаги не передали явно — экспортируем всё.
        if not any((include_review, include_blocking_v2, include_divergent)):
            include_review = include_blocking_v2 = include_divergent = True

        max_pairs = int(options.get('blocking_v2_max_pairs') or 300000)
        max_bucket = int(options.get('blocking_v2_max_bucket') or 120)
        divergent_limit = int(options.get('divergent_limit') or 0)
        divergent_keep_nested = bool(options.get('divergent_keep_nested'))

        snapshot_ts = datetime.now(timezone.utc).isoformat()
        rows: list[dict[str, Any]] = []

        if include_review:
            rows.extend(self._export_pending_reviews(snapshot_ts=snapshot_ts, category_slug=category_slug))
        if include_blocking_v2:
            rows.extend(
                self._export_blocking_v2_pairs(
                    snapshot_ts=snapshot_ts,
                    category_slug=category_slug,
                    max_pairs=max_pairs,
                    max_bucket=max_bucket,
                )
            )
        if include_divergent:
            rows.extend(
                self._export_multi_offer_divergent(
                    snapshot_ts=snapshot_ts,
                    category_slug=category_slug,
                    limit=divergent_limit,
                    keep_nested=divergent_keep_nested,
                )
            )

        summary = self._build_summary(rows=rows, category_slug=category_slug, snapshot_ts=snapshot_ts)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open('w', encoding='utf-8') as f:
            f.write(json.dumps(summary, ensure_ascii=False) + '\n')
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')

        self.stdout.write(self.style.SUCCESS(f'Экспортировано строк: {len(rows)}'))
        self.stdout.write(f'Файл: {out_path}')
        self.stdout.write(
            f"Pair reduction ratio: {summary.get('pair_reduction_ratio', 0.0):.4f} "
            f"({summary.get('blocking_v2_pairs', 0)}/{summary.get('all_possible_pairs', 0)})"
        )

        if golden_path is not None:
            golden_rows = self._build_golden_template(rows=rows, snapshot_ts=snapshot_ts)
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            with golden_path.open('w', encoding='utf-8') as f:
                for row in golden_rows:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
            self.stdout.write(self.style.SUCCESS(f'Golden-template строк: {len(golden_rows)}'))
            self.stdout.write(f'Файл шаблона: {golden_path}')

    def _export_pending_reviews(self, *, snapshot_ts: str, category_slug: str) -> list[dict[str, Any]]:
        qs = (
            MatchReview.objects
            .filter(status=MatchReview.Status.PENDING)
            .select_related('offer__product__category', 'suggested_product__category')
            .order_by('-created_at', '-id')
        )
        if category_slug:
            qs = qs.filter(offer__product__category__slug=category_slug)

        out: list[dict[str, Any]] = []
        for mr in qs.iterator(chunk_size=500):
            offer = mr.offer
            source_product = offer.product if offer else None
            suggested = mr.suggested_product
            if offer is None or source_product is None or suggested is None:
                continue

            a_id, b_id = source_product.pk, suggested.pk
            out.append({
                'row_type': 'pending_review_pair',
                'snapshot_ts': snapshot_ts,
                'pair_key': _pair_key(a_id, b_id),
                'category_slug': source_product.category.slug if source_product.category_id else '',
                'product_a_id': a_id,
                'product_b_id': b_id,
                'product_a_name': source_product.name,
                'product_b_name': suggested.name,
                'sources_a': sorted(set(source_product.offers.values_list('source', flat=True))),
                'sources_b': sorted(set(suggested.offers.values_list('source', flat=True))),
                'signature_dice': signature_dice(
                    model_signature(source_product.name, source_product.brand),
                    model_signature(suggested.name, suggested.brand),
                ),
                'embedding_cosine': float(
                    cosine_similarity(
                        _vec_to_list(source_product.match_embedding),
                        _vec_to_list(suggested.match_embedding),
                    )
                ),
                'review_id': mr.pk,
                'review_score': float(mr.score or 0),
                'signals': mr.signals or {},
                'provenance': {
                    'generator': 'pending_review_queue',
                    'created_at': mr.created_at.isoformat() if mr.created_at else None,
                },
            })
        return out

    def _export_blocking_v2_pairs(
        self,
        *,
        snapshot_ts: str,
        category_slug: str,
        max_pairs: int,
        max_bucket: int,
    ) -> list[dict[str, Any]]:
        products = load_blocking_v2_products(category_slug=category_slug)
        by_id: dict[int, BlockingV2Product] = {p.pk: p for p in products}
        pair_passes, _stats = collect_blocking_v2_pairs(
            products,
            max_pairs=max_pairs,
            max_bucket_size=max_bucket,
        )
        out: list[dict[str, Any]] = []
        for (a_id, b_id), passes in pair_passes.items():
            a = by_id.get(a_id)
            b = by_id.get(b_id)
            if a is None or b is None:
                continue
            out.append({
                'row_type': 'blocking_v2_pair',
                'snapshot_ts': snapshot_ts,
                'pair_key': _pair_key(a_id, b_id),
                'category_slug': a.category_slug or b.category_slug,
                'product_a_id': a_id,
                'product_b_id': b_id,
                'product_a_name': a.name,
                'product_b_name': b.name,
                'sources_a': sorted(a.sources),
                'sources_b': sorted(b.sources),
                'signature_dice': signature_dice(a.sig, b.sig),
                'embedding_cosine': float(cosine_similarity(a.emb, b.emb)),
                'signals': {
                    'passes': sorted(passes),
                    'model_tokens_a': sorted(a.model_tok),
                    'model_tokens_b': sorted(b.model_tok),
                    'offers_count_a': a.offers_count,
                    'offers_count_b': b.offers_count,
                },
                'provenance': {
                    'generator': 'blocking_v2',
                    'passes': sorted(passes),
                },
            })
        return out

    def _export_multi_offer_divergent(
        self,
        *,
        snapshot_ts: str,
        category_slug: str,
        limit: int,
        keep_nested: bool = False,
    ) -> list[dict[str, Any]]:
        qs = (
            Product.objects
            .filter(is_active=True)
            .annotate(offers_count=Count('offers'))
            .filter(offers_count__gt=1)
            .select_related('category')
            .order_by('id')
        )
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        out: list[dict[str, Any]] = []
        for product in qs.iterator(chunk_size=300):
            offers = list(
                Offer.objects
                .filter(product=product)
                .values('id', 'source', 'raw_name')
            )
            grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
            for o in offers:
                raw_name = (o.get('raw_name') or '').strip()
                if not raw_name:
                    continue
                tok = tuple(sorted(model_tokens(model_signature(raw_name, product.brand or ''))))
                if not tok:
                    continue
                grouped[tok].append(o)
            if len(grouped) <= 1:
                continue

            toksets = [frozenset(tok) for tok in grouped]
            kind = _classify_divergence(toksets)
            # nested_subset — не реальное расхождение (один оффер просто
            # дописал спеку). По умолчанию отбрасываем как шум.
            if kind == 'nested_subset' and not keep_nested:
                continue
            suspect_overmerge = len(grouped) >= _DIVERGENCE_OVERMERGE_GROUPS

            out.append({
                'row_type': 'multi_offer_divergent',
                'snapshot_ts': snapshot_ts,
                'pair_key': None,
                'category_slug': product.category.slug if product.category_id else '',
                'product_id': product.pk,
                'product_name': product.name,
                'brand': product.brand,
                'offers_count': product.offers_count,
                'divergence_kind': kind,
                'suspect_overmerge': suspect_overmerge,
                'groups': [
                    {
                        'model_tokens': list(tok),
                        'offer_ids': [x['id'] for x in items],
                        'sources': sorted({x['source'] for x in items if x.get('source')}),
                        'sample_names': [x['raw_name'] for x in items[:3]],
                    }
                    for tok, items in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0]))
                ],
                'provenance': {
                    'generator': 'multi_offer_divergent_detector',
                    'rule': 'distinct_model_tokens_inside_single_product',
                    'divergence_kind': kind,
                    'suspect_overmerge': suspect_overmerge,
                },
            })
            if limit > 0 and len(out) >= limit:
                break
        return out

    def _build_summary(self, *, rows: list[dict[str, Any]], category_slug: str, snapshot_ts: str) -> dict[str, Any]:
        pair_rows = [r for r in rows if r.get('pair_key')]
        blocking_rows = [r for r in rows if r.get('row_type') == 'blocking_v2_pair']
        review_rows = [r for r in rows if r.get('row_type') == 'pending_review_pair']
        divergent_rows = [r for r in rows if r.get('row_type') == 'multi_offer_divergent']

        # Базовый denominator для pair-reduction-ratio:
        # сумма C(n,2) по категориям активных товаров.
        qs = Product.objects.filter(is_active=True)
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        counts_by_cat = (
            qs.values('category_id')
            .annotate(c=Count('id'))
            .values_list('c', flat=True)
        )
        all_possible_pairs = sum((n * (n - 1)) // 2 for n in counts_by_cat)
        pair_reduction_ratio = 0.0
        if all_possible_pairs > 0:
            pair_reduction_ratio = 1.0 - (len(blocking_rows) / all_possible_pairs)

        divergent_by_kind: dict[str, int] = defaultdict(int)
        divergent_overmerge = 0
        for r in divergent_rows:
            divergent_by_kind[r.get('divergence_kind') or 'unknown'] += 1
            if r.get('suspect_overmerge'):
                divergent_overmerge += 1

        return {
            'row_type': 'meta',
            'snapshot_ts': snapshot_ts,
            'category_slug': category_slug,
            'rows_total': len(rows),
            'pair_rows_total': len(pair_rows),
            'pending_review_pairs': len(review_rows),
            'blocking_v2_pairs': len(blocking_rows),
            'multi_offer_divergent': len(divergent_rows),
            'multi_offer_divergent_by_kind': dict(divergent_by_kind),
            'multi_offer_divergent_overmerge': divergent_overmerge,
            'all_possible_pairs': int(all_possible_pairs),
            'pair_reduction_ratio': float(pair_reduction_ratio),
        }

    def _build_golden_template(self, *, rows: list[dict[str, Any]], snapshot_ts: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            pair_key = row.get('pair_key')
            if not pair_key or pair_key in seen:
                continue
            seen.add(pair_key)
            out.append({
                'pair_key': pair_key,
                'snapshot_ts': snapshot_ts,
                'category_slug': row.get('category_slug') or '',
                'product_a_id': row.get('product_a_id'),
                'product_b_id': row.get('product_b_id'),
                'product_a_name': row.get('product_a_name') or '',
                'product_b_name': row.get('product_b_name') or '',
                'label': None,  # 1|0 после ручной разметки
                'notes': '',
                'expected_blocked': True,
                'provenance': {
                    'from_row_type': row.get('row_type'),
                    'passes': ((row.get('provenance') or {}).get('passes') or []),
                    'signals': row.get('signals') or {},
                },
            })
        return out

