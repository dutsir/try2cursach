from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from django.conf import settings
from django.db.models import Q

from ..models import Offer, Product
from .embedding import (
    auto_merge_threshold as embedding_auto_threshold,
    embedding_matching_enabled,
    find_embedding_match,
    review_threshold as embedding_review_threshold,
)
from .constants import (
    AUTO_MERGE_THRESHOLD,
    HARD_REJECT_KEYS,
    NAME_DICE_WEIGHT,
    REVIEW_THRESHOLD,
    SOFT_CONFLICT_PENALTY,
    VARIANT_SPEC_KEYS_BY_CATEGORY,
    WEAK_SOURCES,
    WEIGHTS,
)
from .cross_source import (
    is_discriminating as _sig_discriminating,
    model_tokens as _sig_model_tokens,
    model_signature as _model_signature,
    specs_conflict as _sig_specs_conflict,
)
from .features import Features
from .normalizer import dice as dice_score
from .normalizer import specs_contradict


# Variant-поля которые могут различаться между Products в одной family.
# Полный список используется когда категория неизвестна.
ALL_VARIANT_KEYS: frozenset[str] = frozenset({
    'ram_gb', 'storage_gb', 'screen_in', 'modules_count',
})


def _get_variant_keys_for_category(category_slug: str | None) -> frozenset[str]:
    """Возвращает variant-поля для категории (или дефолт если неизвестна)."""
    if not category_slug:
        return frozenset()
    return VARIANT_SPEC_KEYS_BY_CATEGORY.get(
        category_slug.strip().lower(), frozenset(),
    )

logger = logging.getLogger(__name__)

MatchDecision = Literal['auto_merge', 'review', 'new']


@dataclass
class MatchResult:

    product: Product | None
    score: float
    signals: dict[str, Any] = field(default_factory=dict)
    decision: MatchDecision = 'new'

    @property
    def is_auto_merge(self) -> bool:
        return self.decision == 'auto_merge' and self.product is not None


def hard_reject(product: Product, features: Features) -> tuple[bool, str]:
    """Проверяет — товары категорически НЕ могут быть смержены.

    Учитывает VARIANT_SPEC_KEYS_BY_CATEGORY: variant-поля (ram_gb, storage_gb)
    для категорий где они являются вариантами — НЕ отвергают матч.
    Это позволяет варианты одной модели (Kingston 8GB и 16GB) попадать
    в одну family.
    """
    if features.category_id is not None and product.category_id != features.category_id:
        return True, 'category_mismatch'
    if product.merge_locked:
        return True, 'merge_locked'

    p_brand = (product.brand or '').strip()
    f_brand = (features.brand or '').strip()
    if p_brand and f_brand and p_brand != f_brand:
        return True, 'brand_mismatch'

    p_mpn = (product.vendor_code or '').strip().upper()
    f_mpn = (features.model_code or '').strip().upper()
    if p_mpn and f_mpn and p_mpn != f_mpn:
        return True, 'mpn_mismatch'

    # key_hash — family-уровневый (без variants). Если разные — точно
    # разные семьи модели.
    p_key_hash = (product.key_hash or '').strip()
    f_key_hash = (features.key_hash or '').strip()
    if p_key_hash and f_key_hash and p_key_hash != f_key_hash:
        return True, 'key_hash_mismatch'

    # Определяем какие поля являются variants для этой категории.
    # ВНИМАНИЕ: category_slug может быть не у product (нужно резолвить через FK),
    # но для скорости используем cache на features.category_id.
    category_slug = ''
    if product.category_id:
        # Кэш для производительности
        cat = getattr(product, '_cached_category', None) or product.category
        category_slug = (cat.slug or '').lower() if cat else ''
    variant_keys = _get_variant_keys_for_category(category_slug)

    p_specs: dict[str, Any] = product.specs_fingerprint or {}
    f_specs: dict[str, Any] = features.specs or {}
    for key in HARD_REJECT_KEYS:
        if key == 'model_code':
            continue
        # Если поле — вариант для этой категории, пропускаем
        # (расхождение OK — это разные варианты одной семьи).
        if key in variant_keys:
            continue
        pv = p_specs.get(key)
        fv = f_specs.get(key)
        if pv in (None, '') or fv in (None, ''):
            continue
        if str(pv) != str(fv):
            return True, f'{key}_mismatch'

    return False, ''


_CROSS_SOURCE_SPEC_KEYS: tuple[str, ...] = (
    'ram_gb', 'storage_gb', 'screen_in', 'cpu_family', 'gpu_family',
)


def _cross_source_specs_enabled() -> bool:
    return bool(getattr(settings, 'DEDUP_CROSS_SOURCE_SPECS_ENABLED', True))


def _specs_alignment(product: Product, features: Features) -> tuple[int, int]:
    p_specs = product.specs_fingerprint or {}
    f_specs = features.specs or {}
    matched = 0
    compared = 0
    for key in _CROSS_SOURCE_SPEC_KEYS:
        pv = p_specs.get(key)
        fv = f_specs.get(key)
        if pv in (None, '') or fv in (None, ''):
            continue
        compared += 1
        if str(pv) == str(fv):
            matched += 1
    return matched, compared


def find_cross_source_specs_match(
    features: Features,
    *,
    category_id: int,
) -> MatchResult | None:
    if not _cross_source_specs_enabled():
        return None
    if not features.brand or features.model_code:
        return None
    matched_min = int(getattr(settings, 'DEDUP_CROSS_SOURCE_SPECS_MIN_MATCHED', 2))
    qs = Product.objects.filter(
        category_id=category_id,
        brand=features.brand,
        is_active=True,
    ).exclude(vendor_code='')[:250]
    best: MatchResult | None = None
    for product in qs:
        if product.merge_locked:
            continue
        is_rej, _why = hard_reject(product, features)
        if is_rej:
            continue
        if specs_contradict(product.specs_fingerprint or {}, features.specs):
            continue
        matched, compared = _specs_alignment(product, features)
        if compared < matched_min or matched < matched_min:
            continue
        score_val = 0.86 + 0.02 * min(matched, 4)
        cand = MatchResult(
            product,
            score_val,
            {
                'rule': 'cross_source_specs',
                'specs_matched': matched,
                'specs_compared': compared,
                'brand': features.brand,
            },
            'auto_merge',
        )
        if best is None or cand.score > best.score:
            best = cand
    return best


def _cross_source_signature_enabled() -> bool:
    return bool(getattr(settings, 'DEDUP_CROSS_SOURCE_SIGNATURE_ENABLED', True))


def find_cross_source_signature_match(
    features: Features,
    *,
    category_id: int,
    raw_name: str,
    blocked_ids: frozenset[int],
) -> MatchResult | None:
    """Парс-тайм аналог AUTO-пасса link_cross_source.

    Если у входящего оффера ТОЧНО совпадает «сигнатура модели» (см.
    dedupe/cross_source.py) с существующим мастером того же бренда ИЗ ДРУГОГО
    источника (мастер не в blocked_ids ⇒ у него нет оффера входящего источника)
    и нет конфликта specs → уверенный cross-source матч (auto_merge).

    Это сводит один товар из разных магазинов в один мастер прямо при парсинге.
    Похожие-но-не-точные совпадения сюда НЕ попадают (их ловит батч-команда в
    review-очередь) — на парсинге держим только заведомо безопасные слияния.
    """
    if not _cross_source_signature_enabled():
        return None
    brand = (features.brand or '').strip()
    name = raw_name or ''
    if not brand or not name:
        return None
    sig = _model_signature(name, brand)
    if not _sig_discriminating(sig):
        return None

    qs = (
        Product.objects.filter(category_id=category_id, brand=brand, is_active=True)
        .exclude(id__in=blocked_ids)
        .only('id', 'name', 'brand', 'specs_fingerprint', 'merge_locked')[:250]
    )
    for product in qs:
        if product.merge_locked:
            continue
        if _model_signature(product.name or '', product.brand or '') != sig:
            continue
        if _sig_specs_conflict(product.specs_fingerprint or {}, features.specs):
            continue
        return MatchResult(
            product, 0.99,
            {'rule': 'cross_source_signature', 'sig': sorted(sig), 'brand': brand},
            'auto_merge',
        )
    return None


def _try_embedding_match(
    features: Features,
    *,
    category_id: int,
    raw_name: str = '',
    candidate_ids: list[int] | None = None,
) -> MatchResult | None:
    if not embedding_matching_enabled():
        return None

    try:
        product, sim = find_embedding_match(
            features,
            category_id=category_id,
            raw_name=raw_name,
            candidate_ids=candidate_ids,
        )
    except Exception as e:
        logger.warning('Embedding match failed (continuing with Dice scoring): %s', e)
        return None

    if product is None or sim < embedding_review_threshold():
        return None

    is_rej, why = hard_reject(product, features)
    if is_rej:
        return None

    if product.merge_locked:
        return MatchResult(product, sim, {'rule': 'embedding_locked', 'similarity': sim}, 'review')

    auto_thr = embedding_auto_threshold()
    if features.source in WEAK_SOURCES:
        auto_thr = max(auto_thr, AUTO_MERGE_THRESHOLD + 0.03)

    decision: MatchDecision = 'auto_merge' if sim >= auto_thr else 'review'
    return MatchResult(
        product,
        sim,
        {'rule': 'embedding', 'similarity': round(sim, 4), 'model': 'semantic'},
        decision,
    )


def block_candidates(
    features: Features,
    *,
    category_id: int | None,
    limit: int = 200,
) -> list[Product]:
    cat = category_id or features.category_id
    if cat is None:
        return []

    seen: dict[int, Product] = {}

    def _push(qs):
        for p in qs.only(
            'id', 'name', 'brand', 'vendor_code', 'category_id',
            'specs_fingerprint', 'merge_locked',
        )[:limit]:
            if p.pk not in seen:
                seen[p.pk] = p
                if len(seen) >= limit:
                    return True
        return False

    qs_base = Product.objects.filter(category_id=cat, is_active=True)


    if features.brand and features.model_code:
        if _push(qs_base.filter(brand=features.brand, vendor_code__iexact=features.model_code)):
            return list(seen.values())


    if features.brand:
        if _push(qs_base.filter(brand=features.brand)):
            return list(seen.values())


    anchor = ''
    if features.tokens:
        anchor = max(features.tokens, key=len)
        if len(anchor) < 3:
            anchor = ''
    if anchor:
        _push(qs_base.filter(name__icontains=anchor))

    return list(seen.values())


def score(
    product: Product,
    features: Features,
) -> tuple[float, dict[str, Any]]:
    s = 0.0
    sig: dict[str, Any] = {}

    p_brand = (product.brand or '').strip()
    f_brand = (features.brand or '').strip()
    if p_brand and f_brand and p_brand == f_brand:
        s += WEIGHTS['brand']
        sig['brand'] = WEIGHTS['brand']

    p_mpn = (product.vendor_code or '').strip().upper()
    f_mpn = (features.model_code or '').strip().upper()
    if p_mpn and f_mpn and p_mpn == f_mpn:
        s += WEIGHTS['model_code']
        sig['model_code'] = WEIGHTS['model_code']

    p_specs: dict[str, Any] = product.specs_fingerprint or {}
    f_specs: dict[str, Any] = features.specs or {}

    for key in ('screen_in', 'ram_gb', 'storage_gb', 'cpu_family', 'gpu_family'):
        pv = p_specs.get(key)
        fv = f_specs.get(key)
        if pv in (None, '') or fv in (None, ''):
            continue
        if str(pv) == str(fv):
            w = WEIGHTS.get(key, 0.0)
            s += w
            sig[key] = w
        else:
            penalty = SOFT_CONFLICT_PENALTY.get(key, 0.0)
            if penalty:
                s -= penalty
                sig[f'{key}_conflict'] = -penalty

    p_color = (p_specs.get('color') or '')
    f_color = (f_specs.get('color') or '')
    if p_color and f_color and p_color != f_color:
        s -= SOFT_CONFLICT_PENALTY['color']
        sig['color_conflict'] = -SOFT_CONFLICT_PENALTY['color']


    from .normalizer import _tokens as tokenize
    p_tokens = tokenize(product.name or '')
    name_score = dice_score(features.tokens, p_tokens)
    if name_score > 0:
        weighted = name_score * NAME_DICE_WEIGHT
        s += weighted
        sig['name_dice'] = round(name_score, 3)
        sig['name_dice_weighted'] = round(weighted, 3)

    return max(0.0, min(s, 1.5)), sig


def _decide(
    product: Product | None,
    score_value: float,
    features: Features,
) -> MatchDecision:
    if product is None:
        return 'new'
    if product.merge_locked:
        return 'review'
    auto_thr = AUTO_MERGE_THRESHOLD
    if features.source in WEAK_SOURCES:
        auto_thr = AUTO_MERGE_THRESHOLD + 0.05
    if score_value >= auto_thr:
        return 'auto_merge'
    if score_value >= REVIEW_THRESHOLD:
        return 'review'
    return 'new'


def _auto_identity_guard(
    *,
    product: Product,
    features: Features,
    raw_name: str,
    signals: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Safety gate for AUTO decisions.

    Разрешаем AUTO только при сильной идентичности SKU:
    - exact MPN, или
    - совпадающие model_tokens между входным именем и кандидатом.
    """
    sig = signals or {}
    if str(sig.get('rule') or '') == 'mpn_exact':
        return True, ''

    p_mpn = (product.vendor_code or '').strip().upper()
    f_mpn = (features.model_code or '').strip().upper()
    if p_mpn and f_mpn and p_mpn == f_mpn:
        return True, ''

    product_tok = _sig_model_tokens(_model_signature(product.name or '', product.brand or ''))
    incoming_tok = _sig_model_tokens(_model_signature(raw_name or '', features.brand or product.brand or ''))
    if product_tok and incoming_tok:
        if product_tok == incoming_tok:
            shared = product_tok & incoming_tok
            # Токены вида "2tb", "16gb", "104keys" слишком общие и не должны
            # в одиночку разрешать AUTO merge.
            generic_suffixes = ('gb', 'tb', 'mhz', 'hz', 'w', 'mm', 'keys', 'key', 'pcs')
            has_specific = False
            for token in shared:
                low = token.lower()
                has_letters = any(ch.isalpha() for ch in low)
                has_digits = any(ch.isdigit() for ch in low)
                if not (has_letters and has_digits):
                    continue
                if len(low) < 5:
                    continue
                if any(low.endswith(s) for s in generic_suffixes):
                    continue
                has_specific = True
                break
            if has_specific:
                return True, ''
            return False, 'identity_tokens_too_generic'
        return False, 'model_tokens_mismatch'
    if product_tok or incoming_tok:
        return False, 'model_tokens_partial'

    return False, 'missing_strong_identity'


# Источники, у которых ВНУТРИ одного источника бывают легитимные дубли
# (несколько продавцов/карточек одного товара) → нужна внутренняя дедупликация.
# Для всех остальных источников (dns, citilink, mvideo, regard) товары в рамках
# категории уникальны по url/sku, поэтому два разных оффера одного источника
# НЕ должны схлопываться в один Product.
WITHIN_SOURCE_DEDUP_SOURCES: frozenset[str] = frozenset({'wb'})


def _same_source_blocked_ids(features: Features, cat: int) -> frozenset[int]:
    """product_id мастеров, у которых уже есть оффер входящего источника.

    Для источников вне WITHIN_SOURCE_DEDUP_SOURCES такие мастера запрещены как
    цель мёрджа — иначе разные товары одного источника склеятся в один Product.
    """
    src = (features.source or '').strip().lower()
    if not src or src in WITHIN_SOURCE_DEDUP_SOURCES:
        return frozenset()
    return frozenset(
        Offer.objects.filter(product__category_id=cat, source=src)
        .values_list('product_id', flat=True),
    )


def find_master(
    features: Features,
    *,
    category_id: int | None = None,
    raw_name: str = '',
) -> MatchResult:
    cat = category_id or features.category_id
    if cat is None:
        return MatchResult(None, 0.0, {'error': 'no_category'}, 'new')

    blocked_ids = _same_source_blocked_ids(features, cat)

    if features.brand and features.model_code:
        det_qs = Product.objects.filter(
            category_id=cat,
            brand=features.brand,
            vendor_code__iexact=features.model_code,
            is_active=True,
        ).exclude(id__in=blocked_ids)
        for det in det_qs[:5]:
            if det.merge_locked:

                return MatchResult(
                    det, 1.0,
                    {'rule': 'mpn_exact_locked'}, 'review',
                )
            if specs_contradict(det.specs_fingerprint or {}, features.specs):


                continue
            return MatchResult(
                det, 1.0,
                {'rule': 'mpn_exact', 'mpn': features.model_code, 'brand': features.brand},
                'auto_merge',
            )

    cross = find_cross_source_specs_match(features, category_id=cat)
    if cross is not None and not (cross.product and cross.product.pk in blocked_ids):
        if cross.decision == 'auto_merge' and cross.product is not None:
            ok, why = _auto_identity_guard(
                product=cross.product,
                features=features,
                raw_name=raw_name,
                signals=cross.signals,
            )
            if not ok:
                cross.decision = 'review'
                cross.signals = {**(cross.signals or {}), 'demoted_reason': why}
        return cross

    sig_match = find_cross_source_signature_match(
        features, category_id=cat, raw_name=raw_name, blocked_ids=blocked_ids,
    )
    if sig_match is not None:
        if sig_match.decision == 'auto_merge' and sig_match.product is not None:
            ok, why = _auto_identity_guard(
                product=sig_match.product,
                features=features,
                raw_name=raw_name,
                signals=sig_match.signals,
            )
            if not ok:
                sig_match.decision = 'review'
                sig_match.signals = {**(sig_match.signals or {}), 'demoted_reason': why}
        return sig_match

    candidates = block_candidates(features, category_id=cat)
    if blocked_ids:
        candidates = [c for c in candidates if c.pk not in blocked_ids]
    if not candidates:
        return MatchResult(None, 0.0, {'rule': 'no_candidates'}, 'new')

    best: MatchResult | None = None
    best_signals: dict[str, Any] = {}
    rejected: list[tuple[int, str]] = []
    for c in candidates:
        is_rej, why = hard_reject(c, features)
        if is_rej:
            rejected.append((c.pk, why))
            continue
        s, sig = score(c, features)
        if best is None or s > best.score:
            best_signals = sig
            best = MatchResult(c, s, sig, 'new')

    if best is None:
        emb = _try_embedding_match(
            features,
            category_id=cat,
            raw_name=raw_name,
            candidate_ids=[c.pk for c in candidates],
        )
        if emb is not None:
            if emb.decision == 'auto_merge' and emb.product is not None:
                ok, why = _auto_identity_guard(
                    product=emb.product,
                    features=features,
                    raw_name=raw_name,
                    signals=emb.signals,
                )
                if not ok:
                    emb.decision = 'review'
                    emb.signals = {**(emb.signals or {}), 'demoted_reason': why}
            return emb
        return MatchResult(
            None, 0.0,
            {'rule': 'all_rejected', 'rejected': rejected[:5], 'candidates_seen': len(candidates)},
            'new',
        )

    decision = _decide(best.product, best.score, features)
    best.decision = decision
    best.signals = {
        'rule': 'weighted_score',
        **best_signals,
        'candidates_seen': len(candidates),
        'rejected_count': len(rejected),
    }


    if decision == 'auto_merge':
        hard_signals = sum(
            1 for k in ('brand', 'model_code', 'ram_gb', 'storage_gb', 'screen_in', 'cpu_family', 'gpu_family')
            if k in best_signals
        )
        if 'model_code' not in best_signals and hard_signals < 3:
            best.decision = 'review'
            best.signals['demoted_reason'] = 'insufficient_hard_signals'
        elif best.product is not None:
            ok, why = _auto_identity_guard(
                product=best.product,
                features=features,
                raw_name=raw_name,
                signals=best.signals,
            )
            if not ok:
                best.decision = 'review'
                best.signals['demoted_reason'] = why

    if best.decision in ('new', 'review') or best.score < AUTO_MERGE_THRESHOLD:
        emb = _try_embedding_match(
            features,
            category_id=cat,
            raw_name=raw_name,
            candidate_ids=[c.pk for c in candidates],
        )
        if emb is not None and emb.score > best.score:
            if emb.decision == 'auto_merge' and emb.product is not None:
                ok, why = _auto_identity_guard(
                    product=emb.product,
                    features=features,
                    raw_name=raw_name,
                    signals=emb.signals,
                )
                if not ok:
                    emb.decision = 'review'
                    emb.signals = {**(emb.signals or {}), 'demoted_reason': why}
            return emb

    return best


__all__ = (
    'MatchDecision',
    'MatchResult',
    'block_candidates',
    'find_cross_source_specs_match',
    'find_master',
    'hard_reject',
    'score',
)
