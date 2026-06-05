from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
import re
from typing import Any

from django.db.models import Count

from apps.products.models import Offer, Product

from .cross_source import model_signature, model_tokens, specs_conflict

_NAME_CLEAN_RE = re.compile(r'[^0-9a-zа-я]+', flags=re.IGNORECASE)


@dataclass
class BlockingV2Product:
    pk: int
    category_id: int
    category_slug: str
    name: str
    brand: str
    vendor_code: str
    specs: dict[str, Any]
    sources: frozenset[str]
    offers_count: int
    sig: frozenset[str]
    model_tok: frozenset[str]
    emb: list[float] | None


def _normalize_brand(brand: str) -> str:
    return (brand or '').strip().lower()


def _normalize_mpn(vendor_code: str) -> str:
    raw = (vendor_code or '').strip().upper()
    return re.sub(r'[^0-9A-Z]+', '', raw)


def _word_trigrams(name: str) -> set[str]:
    clean = _NAME_CLEAN_RE.sub(' ', (name or '').lower())
    out: set[str] = set()
    for word in clean.split():
        if len(word) < 3:
            continue
        if len(word) == 3:
            out.add(word)
            continue
        for i in range(len(word) - 2):
            out.add(word[i:i + 3])
    return out


def _pair_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _is_cross_source_pair(a: BlockingV2Product, b: BlockingV2Product) -> bool:
    return not (set(a.sources) & set(b.sources))


def _can_be_candidate(a: BlockingV2Product, b: BlockingV2Product) -> bool:
    if a.pk == b.pk:
        return False
    if a.category_id != b.category_id:
        return False
    if not _is_cross_source_pair(a, b):
        return False
    if specs_conflict(a.specs, b.specs):
        return False
    return True


def _add_bucket_pairs(
    *,
    pair_passes: dict[tuple[int, int], set[str]],
    bucket: list[BlockingV2Product],
    pass_name: str,
    max_pairs: int,
) -> None:
    for left, right in combinations(bucket, 2):
        if len(pair_passes) >= max_pairs:
            return
        if not _can_be_candidate(left, right):
            continue
        key = _pair_key(left.pk, right.pk)
        pair_passes.setdefault(key, set()).add(pass_name)


def load_blocking_v2_products(
    *,
    category_slug: str = '',
    limit_products: int = 0,
) -> list[BlockingV2Product]:
    qs = (
        Product.objects
        .filter(is_active=True, merge_locked=False)
        .select_related('category')
        .annotate(offers_count=Count('offers'))
        .filter(offers_count__gt=0)
        .order_by('id')
    )
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if limit_products > 0:
        qs = qs[:limit_products]

    products = list(qs)
    if not products:
        return []

    src_map: dict[int, set[str]] = defaultdict(set)
    for pid, src in (
        Offer.objects
        .filter(product_id__in=[p.pk for p in products])
        .values_list('product_id', 'source')
    ):
        if src:
            src_map[pid].add((src or '').lower())

    out: list[BlockingV2Product] = []
    for p in products:
        sig = model_signature(p.name or '', p.brand or '')
        model_tok = model_tokens(sig)
        emb = p.match_embedding
        out.append(
            BlockingV2Product(
                pk=p.pk,
                category_id=p.category_id,
                category_slug=(p.category.slug if p.category else ''),
                name=p.name or '',
                brand=p.brand or '',
                vendor_code=p.vendor_code or '',
                specs=p.specs_fingerprint or {},
                sources=frozenset(src_map.get(p.pk, set())),
                offers_count=int(getattr(p, 'offers_count', 0) or 0),
                sig=sig,
                model_tok=model_tok,
                emb=[float(x) for x in emb] if emb is not None else None,
            )
        )
    return out


def collect_blocking_v2_pairs(
    products: list[BlockingV2Product],
    *,
    max_pairs: int = 200_000,
    max_bucket_size: int = 120,
) -> tuple[dict[tuple[int, int], set[str]], dict[str, int]]:
    stats: dict[str, int] = {
        'products': len(products),
        'pairs': 0,
        'bucket_mpn': 0,
        'bucket_model_tokens': 0,
        'bucket_brand_trigram': 0,
        'bucket_brand_trigram_skipped': 0,
    }
    pair_passes: dict[tuple[int, int], set[str]] = {}

    # PASS-1: category + exact MPN (самый точный сигнал).
    by_mpn: dict[tuple[int, str], list[BlockingV2Product]] = defaultdict(list)
    for p in products:
        mpn = _normalize_mpn(p.vendor_code)
        if len(mpn) < 4:
            continue
        by_mpn[(p.category_id, mpn)].append(p)
    for bucket in by_mpn.values():
        if len(bucket) < 2:
            continue
        stats['bucket_mpn'] += 1
        _add_bucket_pairs(
            pair_passes=pair_passes,
            bucket=bucket,
            pass_name='category_mpn_exact',
            max_pairs=max_pairs,
        )
        if len(pair_passes) >= max_pairs:
            stats['pairs'] = len(pair_passes)
            return pair_passes, stats

    # PASS-2: category + идентичные model_tokens(sig).
    by_model_tokens: dict[tuple[int, tuple[str, ...]], list[BlockingV2Product]] = defaultdict(list)
    for p in products:
        if not p.model_tok:
            continue
        by_model_tokens[(p.category_id, tuple(sorted(p.model_tok)))].append(p)
    for bucket in by_model_tokens.values():
        if len(bucket) < 2:
            continue
        stats['bucket_model_tokens'] += 1
        _add_bucket_pairs(
            pair_passes=pair_passes,
            bucket=bucket,
            pass_name='category_model_tokens',
            max_pairs=max_pairs,
        )
        if len(pair_passes) >= max_pairs:
            stats['pairs'] = len(pair_passes)
            return pair_passes, stats

    # PASS-3: category + brand + name-trigram.
    by_brand_trigram: dict[tuple[int, str, str], list[BlockingV2Product]] = defaultdict(list)
    for p in products:
        brand = _normalize_brand(p.brand)
        if not brand:
            continue
        for tri in _word_trigrams(p.name):
            by_brand_trigram[(p.category_id, brand, tri)].append(p)

    for bucket in by_brand_trigram.values():
        if len(bucket) < 2:
            continue
        if len(bucket) > max_bucket_size:
            stats['bucket_brand_trigram_skipped'] += 1
            continue
        stats['bucket_brand_trigram'] += 1
        _add_bucket_pairs(
            pair_passes=pair_passes,
            bucket=bucket,
            pass_name='category_brand_name_trigram',
            max_pairs=max_pairs,
        )
        if len(pair_passes) >= max_pairs:
            stats['pairs'] = len(pair_passes)
            return pair_passes, stats

    stats['pairs'] = len(pair_passes)
    return pair_passes, stats

