from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.text import slugify

from ..models import Category, MergeAuditLog, Offer, Product
from .audit import enqueue_review, write_audit
from .embedding import pick_display_name, sync_product_embedding
from .features import Features
from .matcher import MatchResult, find_master
from .normalizer import normalize_offer, normalize_offer_url

logger = logging.getLogger(__name__)


@dataclass
class OfferUpsertResult:
    offer: Offer
    offer_created: bool
    product_created: bool
    match_reason: str
    decision: str
    score: float


def is_v2_enabled() -> bool:
    return bool(getattr(settings, 'DEDUP_V2', False))


def is_shadow_enabled() -> bool:
    return bool(getattr(settings, 'DEDUP_SHADOW', False))


def _rematch_on_update_enabled() -> bool:
    return bool(getattr(settings, 'DEDUP_REMATCH_ON_UPDATE', True))


def _rematch_cooldown_hours() -> int:
    return int(getattr(settings, 'DEDUP_REMATCH_COOLDOWN_HOURS', 24))


def _audit_decision_for_match(decision: str) -> str:
    return {
        'auto_merge': MergeAuditLog.Decision.AUTO_MERGE,
        'review': MergeAuditLog.Decision.REVIEW,
        'new': MergeAuditLog.Decision.NEW,
    }.get(decision, MergeAuditLog.Decision.NEW)


def _is_offer_rematch_cooldown(offer: Offer) -> bool:
    hours = _rematch_cooldown_hours()
    if hours <= 0:
        return False
    cutoff = timezone.now() - timezone.timedelta(hours=hours)
    return MergeAuditLog.objects.filter(
        offer=offer,
        decision=MergeAuditLog.Decision.AUTO_MERGE,
        created_at__gte=cutoff,
    ).exclude(from_product_id=models.F('to_product_id')).exists()


def _make_unique_slug(name: str, mpn: str) -> str:
    base = slugify(name or '', allow_unicode=True)[:480] or 'product'
    if mpn:
        slug_mpn = slugify(mpn, allow_unicode=True)[:48]
        slug = f'{base}-{slug_mpn}' if slug_mpn else base
    else:
        slug = base
    n = 0
    while Product.objects.filter(slug=slug).exists():
        n += 1
        slug = f'{slug[:480]}-d{n}'[:512]
    return slug


def _features_to_product(
    features: Features,
    *,
    name: str,
    image_url: str,
    fallback_url: str,
    category: Category,
) -> tuple[Product, bool]:
    brand = (features.brand or '').strip()[:64]
    mpn = (features.model_code or '').strip()[:100]
    if brand and mpn:
        existing = (
            Product.objects
            .filter(category=category, brand=brand, vendor_code=mpn)
            .first()
        )
        if existing:
            _touch_product(existing, features=features, name=name, image_url=image_url)
            return existing, False

    display = pick_display_name(name) or name
    payload = dict(
        name=display[:512],
        slug=_make_unique_slug(name, features.model_code),
        category=category,
        vendor_code=mpn,
        brand=brand,
        specs_fingerprint=features.specs,
        key_hash=features.key_hash,
        url=fallback_url or '',
        image_url=image_url or '',
        is_active=True,
        last_parsed_at=timezone.now(),
    )
    try:
        product = Product.objects.create(**payload)
        sync_product_embedding(product, features, name)
        return product, True
    except IntegrityError:
        if brand and mpn:
            existing = (
                Product.objects
                .filter(category=category, brand=brand, vendor_code=mpn)
                .first()
            )
            if existing:
                _touch_product(existing, features=features, name=name, image_url=image_url)
                return existing, False
        raise


def _touch_product(product: Product, *, features: Features, name: str, image_url: str) -> None:
    updates: list[str] = []
    display = pick_display_name(name, product.name)
    if display and display != (product.name or ''):
        product.name = display[:512]
        updates.append('name')
    if image_url and not product.image_url:
        product.image_url = image_url[:1024]
        updates.append('image_url')
    if features.brand and not (product.brand or '').strip():
        product.brand = features.brand[:64]
        updates.append('brand')
    if features.model_code and not (product.vendor_code or '').strip():
        product.vendor_code = features.model_code[:100]
        updates.append('vendor_code')

    current_specs: dict[str, Any] = product.specs_fingerprint or {}
    merged = dict(current_specs)
    changed_specs = False
    for k, v in (features.specs or {}).items():
        if k not in merged or merged.get(k) in (None, ''):
            merged[k] = v
            changed_specs = True
    if changed_specs:
        product.specs_fingerprint = merged
        updates.append('specs_fingerprint')
    if features.key_hash != (product.key_hash or ''):
        product.key_hash = features.key_hash
        updates.append('key_hash')

    product.last_parsed_at = timezone.now()
    updates.extend(['last_parsed_at', 'updated_at'])
    product.save(update_fields=list(dict.fromkeys(updates)))
    if product.match_embedding is None:
        sync_product_embedding(product, features, name)


def _update_offer(
    offer: Offer,
    *,
    name: str,
    features: Features,
    match: MatchResult | None,
    image_url: str,
    is_available: bool,
    sku: str,
) -> None:
    changed: list[str] = []
    if image_url and offer.image_url != image_url:
        offer.image_url = image_url[:1024]
        changed.append('image_url')
    if sku and offer.source_sku != sku:
        offer.source_sku = sku[:128]
        changed.append('source_sku')
    if name and offer.raw_name != name:
        offer.raw_name = name
        changed.append('raw_name')
    new_features_jsonable = features.to_jsonable()
    if (offer.normalized_features or {}) != new_features_jsonable:
        offer.normalized_features = new_features_jsonable
        changed.append('normalized_features')
    if features.model_code and offer.mpn_extracted != features.model_code:
        offer.mpn_extracted = features.model_code[:64]
        changed.append('mpn_extracted')
    if offer.is_available != is_available:
        offer.is_available = is_available
        changed.append('is_available')
    if match is not None:
        new_signals = {**(match.signals or {}), 'decision': match.decision}
        if (offer.match_signals or {}) != new_signals:
            offer.match_signals = new_signals
            changed.append('match_signals')
        new_conf = Decimal(str(round(match.score, 2)))
        if Decimal(str(offer.confidence or 0)) != new_conf:
            offer.confidence = new_conf
            changed.append('confidence')
    offer.last_seen_at = timezone.now()
    changed.extend(['last_seen_at', 'updated_at'])
    offer.save(update_fields=list(dict.fromkeys(changed)))


def _resolve_product_for_match(
    match: MatchResult,
    *,
    features: Features,
    name: str,
    image_url: str,
    fallback_url: str,
    category: Category,
) -> tuple[Product, bool, str]:
    if match.decision == 'auto_merge' and match.product is not None:
        product = match.product
        _touch_product(product, features=features, name=name, image_url=image_url)
        rule = match.signals.get('rule', 'auto_merge') if isinstance(match.signals, dict) else 'auto_merge'
        return product, False, rule

    product, product_created = _features_to_product(
        features,
        name=name,
        image_url=image_url,
        fallback_url=fallback_url,
        category=category,
    )
    if match.decision == 'review' and match.product is not None:
        return product, product_created, 'review_pending'
    return product, product_created, 'new'


def _apply_rematch_to_existing_offer(
    offer: Offer,
    *,
    match: MatchResult,
    features: Features,
    name: str,
    image_url: str,
    category: Category,
) -> tuple[str, str]:
    current_product = offer.product
    match_reason = 'existing_rematched'
    audit_decision = MergeAuditLog.Decision.UPDATE

    target = match.product
    if (
        match.decision == 'auto_merge'
        and target is not None
        and target.pk != current_product.pk
    ):
        if _is_offer_rematch_cooldown(offer):
            enqueue_review(
                offer=offer,
                suggested=target,
                score=match.score,
                signals={**(match.signals or {}), 'rejected': 'cooldown_active'},
            )
            write_audit(
                offer=offer,
                decision=MergeAuditLog.Decision.REVIEW,
                actor=MergeAuditLog.Actor.AUTO,
                score=match.score,
                signals={
                    **(match.signals or {}),
                    'rematch': 'cooldown_skipped',
                    'suggested_product_id': target.pk,
                },
                from_product=current_product,
                to_product=target,
            )
            match_reason = 'existing_cooldown_review'
            audit_decision = MergeAuditLog.Decision.REVIEW
        else:
            offer.product = target
            offer.save(update_fields=['product', 'updated_at'])
            _touch_product(target, features=features, name=name, image_url=image_url)
            write_audit(
                offer=offer,
                decision=MergeAuditLog.Decision.AUTO_MERGE,
                actor=MergeAuditLog.Actor.AUTO,
                score=match.score,
                signals={**(match.signals or {}), 'rematch': True},
                from_product=current_product,
                to_product=target,
            )
            match_reason = match.signals.get('rule', 'auto_merge_rematch')
            audit_decision = MergeAuditLog.Decision.AUTO_MERGE
    elif (
        match.decision == 'review'
        and target is not None
        and target.pk != current_product.pk
    ):
        enqueue_review(
            offer=offer,
            suggested=target,
            score=match.score,
            signals=match.signals,
        )
        write_audit(
            offer=offer,
            decision=MergeAuditLog.Decision.REVIEW,
            actor=MergeAuditLog.Actor.AUTO,
            score=match.score,
            signals={
                **(match.signals or {}),
                'rematch': True,
                'suggested_product_id': target.pk,
                'kept_product_id': current_product.pk,
            },
            from_product=current_product,
            to_product=current_product,
        )
        match_reason = 'existing_review_queued'
        audit_decision = MergeAuditLog.Decision.REVIEW
    else:
        write_audit(
            offer=offer,
            decision=_audit_decision_for_match(match.decision),
            actor=MergeAuditLog.Actor.AUTO,
            score=match.score,
            signals={**(match.signals or {}), 'rematch': True, 'product_unchanged': True},
            from_product=current_product,
            to_product=current_product,
        )
        match_reason = 'existing'

    _touch_product(offer.product, features=features, name=name, image_url=image_url)
    return match_reason, audit_decision


def _finalize_existing_offer(
    offer: Offer,
    *,
    features: Features,
    name: str,
    image_url: str,
    is_available: bool,
    sku: str,
    category: Category,
    idempotent_rule: str,
) -> OfferUpsertResult:
    if _rematch_on_update_enabled():
        match = find_master(features, category_id=category.pk, raw_name=name)
        _update_offer(
            offer,
            name=name,
            features=features,
            match=match,
            image_url=image_url,
            is_available=is_available,
            sku=sku,
        )
        match_reason, audit_decision = _apply_rematch_to_existing_offer(
            offer,
            match=match,
            features=features,
            name=name,
            image_url=image_url,
            category=category,
        )
        return OfferUpsertResult(
            offer=offer,
            offer_created=False,
            product_created=False,
            match_reason=match_reason,
            decision=audit_decision,
            score=match.score,
        )

    _update_offer(
        offer,
        name=name,
        features=features,
        match=None,
        image_url=image_url,
        is_available=is_available,
        sku=sku,
    )
    _touch_product(offer.product, features=features, name=name, image_url=image_url)
    write_audit(
        offer=offer,
        decision=MergeAuditLog.Decision.UPDATE,
        actor=MergeAuditLog.Actor.AUTO,
        score=float(offer.confidence or 0),
        signals={'rule': idempotent_rule},
        from_product=offer.product,
        to_product=offer.product,
    )
    return OfferUpsertResult(
        offer=offer,
        offer_created=False,
        product_created=False,
        match_reason='existing',
        decision=MergeAuditLog.Decision.UPDATE,
        score=float(offer.confidence or 0),
    )


@transaction.atomic
def upsert_offer(
    *,
    category: Category,
    source: str,
    name: str,
    url: str,
    vendor_code: str = '',
    image_url: str = '',
    is_available: bool = True,
    mpn_hint: str = '',
) -> OfferUpsertResult:
    src = (source or '').lower()
    canonical_url = normalize_offer_url(url, source=src) or url

    features = normalize_offer(
        name=name,
        source=src,
        category_id=category.pk,
        sku=vendor_code or '',
        url=canonical_url,
        mpn_hint=mpn_hint,
    )

    offer = (
        Offer.objects
        .filter(source=src, url=canonical_url)
        .select_related('product')
        .first()
    )
    if offer:
        return _finalize_existing_offer(
            offer,
            features=features,
            name=name,
            image_url=image_url,
            is_available=is_available,
            sku=vendor_code or '',
            category=category,
            idempotent_rule='idempotent_url',
        )

    sku = (vendor_code or '').strip()
    if sku:
        offer_by_sku = (
            Offer.objects
            .filter(source=src, source_sku=sku)
            .select_related('product')
            .first()
        )
        if offer_by_sku:
            offer_by_sku.url = canonical_url
            offer_by_sku.save(update_fields=['url', 'updated_at'])
            return _finalize_existing_offer(
                offer_by_sku,
                features=features,
                name=name,
                image_url=image_url,
                is_available=is_available,
                sku=sku,
                category=category,
                idempotent_rule='idempotent_sku',
            )

    match = find_master(features, category_id=category.pk, raw_name=name)
    product, product_created, match_reason = _resolve_product_for_match(
        match,
        features=features,
        name=name,
        image_url=image_url,
        fallback_url=canonical_url,
        category=category,
    )

    offer = Offer.objects.create(
        product=product,
        source=src,
        url=canonical_url,
        source_sku=sku[:128],
        vendor_code=sku[:128],
        mpn_extracted=features.model_code[:64],
        raw_name=name,
        normalized_features=features.to_jsonable(),
        match_signals={**(match.signals or {}), 'decision': match.decision},
        confidence=Decimal(str(round(match.score, 2))),
        image_url=(image_url or '')[:1024],
        is_available=is_available,
        last_seen_at=timezone.now(),
    )

    if match.decision == 'review' and match.product is not None:
        enqueue_review(
            offer=offer,
            suggested=match.product,
            score=match.score,
            signals=match.signals,
        )

    write_audit(
        offer=offer,
        decision=_audit_decision_for_match(match.decision),
        actor=MergeAuditLog.Actor.AUTO,
        score=match.score,
        signals=match.signals,
        from_product=None,
        to_product=product,
    )
    logger.info(
        'upsert_offer[%s]: decision=%s score=%.3f product_id=%s offer_id=%s',
        src, match.decision, match.score, product.pk, offer.pk,
    )
    return OfferUpsertResult(
        offer=offer,
        offer_created=True,
        product_created=product_created,
        match_reason=match_reason,
        decision=match.decision,
        score=match.score,
    )


def shadow_match(
    *,
    category: Category,
    source: str,
    name: str,
    url: str,
    vendor_code: str = '',
    mpn_hint: str = '',
) -> MatchResult:
    src = (source or '').lower()
    canonical_url = normalize_offer_url(url, source=src) or url
    features = normalize_offer(
        name=name,
        source=src,
        category_id=category.pk,
        sku=vendor_code or '',
        url=canonical_url,
        mpn_hint=mpn_hint,
    )
    result = find_master(features, category_id=category.pk, raw_name=name)
    write_audit(
        offer=None,
        decision=_audit_decision_for_match(result.decision),
        actor=MergeAuditLog.Actor.SHADOW,
        score=result.score,
        signals={'shadow': True, 'name': name[:200], 'source': src, **(result.signals or {})},
        from_product=None,
        to_product=result.product,
    )
    return result


__all__ = (
    'OfferUpsertResult',
    'is_shadow_enabled',
    'is_v2_enabled',
    'shadow_match',
    'upsert_offer',
)
