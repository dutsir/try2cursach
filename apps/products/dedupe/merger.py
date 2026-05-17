from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Model

from ..models import MergeAuditLog, Offer, Product
from .audit import write_audit
from .normalizer import normalize_offer, specs_contradict

logger = logging.getLogger(__name__)
_TRANSITIVITY_SAMPLE_LIMIT = 5


def _one_to_many_fields() -> list[Any]:
    fields: list[Any] = []
    for f in Product._meta.get_fields():
        if not (getattr(f, 'one_to_many', False) or getattr(f, 'one_to_one', False)):
            continue
        if f.related_model is None or getattr(f, 'field', None) is None:
            continue
        fields.append(f)
    return fields


def _move_related(model: type[Model], fk_name: str, donor: Product, canonical: Product) -> None:
    try:
        with transaction.atomic():
            moved = (
                model.objects
                .filter(**{fk_name: donor})
                .update(**{fk_name: canonical})
            )
    except IntegrityError as exc:
        logger.info(
            'merge: %s.%s — batch update конфликтует (%s), per-row',
            model.__name__, fk_name, exc.__class__.__name__,
        )
    else:
        if moved:
            logger.info('merge: %s.%s — перенесено %d', model.__name__, fk_name, moved)
        return

    moved = 0
    deduped = 0
    for obj in list(model.objects.filter(**{fk_name: donor})):
        try:
            with transaction.atomic():
                setattr(obj, fk_name, canonical)
                obj.save(update_fields=[fk_name])
            moved += 1
        except IntegrityError:
            try:
                with transaction.atomic():
                    obj.delete()
                deduped += 1
            except Exception as exc:
                logger.warning(
                    'merge: %s id=%s не удалось ни перенести, ни удалить: %s',
                    model.__name__, getattr(obj, 'pk', '?'), exc,
                )
    logger.info(
        'merge: %s.%s — перенесено %d, дублей удалено %d',
        model.__name__, fk_name, moved, deduped,
    )


def _offer_features_for_product(offer: Offer, product: Product) -> tuple[str, str, dict[str, Any]]:
    raw_name = (offer.raw_name or '').strip() or product.name
    normalized = offer.normalized_features or {}
    if normalized:
        brand = str(normalized.get('brand') or product.brand or '').strip().lower()
        model_code = str(
            normalized.get('model_code') or offer.mpn_extracted or product.vendor_code or ''
        ).strip().upper()
        specs_raw = normalized.get('specs') or {}
        specs = specs_raw if isinstance(specs_raw, dict) else {}
        return brand, model_code, specs
    features = normalize_offer(
        name=raw_name,
        source=offer.source,
        category_id=product.category_id,
        sku=offer.source_sku or offer.vendor_code or '',
        url=offer.url,
        mpn_hint=offer.mpn_extracted or '',
    )
    return features.brand, features.model_code, features.specs or {}


def _passes_transitivity_guard(donor: Product, canonical: Product) -> tuple[bool, str]:
    if donor.category_id != canonical.category_id:
        return False, 'category_mismatch'
    if donor.merge_locked or canonical.merge_locked:
        return False, 'merge_locked'
    donor_offers = list(
        Offer.objects.filter(product=donor).order_by('-updated_at')[:_TRANSITIVITY_SAMPLE_LIMIT]
    )
    canon_offers = list(
        Offer.objects.filter(product=canonical).order_by('-updated_at')[:_TRANSITIVITY_SAMPLE_LIMIT]
    )
    if not donor_offers or not canon_offers:
        return True, ''

    for d_offer in donor_offers:
        d_brand, d_model, d_specs = _offer_features_for_product(d_offer, donor)
        for c_offer in canon_offers:
            c_brand, c_model, c_specs = _offer_features_for_product(c_offer, canonical)
            if d_brand and c_brand and d_brand != c_brand:
                return False, 'transitivity_brand_conflict'
            if d_model and c_model and d_model != c_model:
                return False, 'transitivity_mpn_conflict'
            if specs_contradict(d_specs, c_specs):
                return False, 'transitivity_specs_conflict'
    return True, ''


def apply_merge(
    *,
    donor: Product,
    canonical: Product,
    score: float = 1.0,
    signals: dict[str, Any] | None = None,
    actor: str = MergeAuditLog.Actor.AUTO,
    run_id: str = '',
) -> None:
    if donor.pk == canonical.pk:
        return
    if canonical.merge_locked:
        write_audit(
            offer=None, decision=MergeAuditLog.Decision.REVIEW,
            actor=actor, score=score, signals={'rejected': 'canonical_locked', **(signals or {})},
            from_product=donor, to_product=canonical, run_id=run_id,
        )
        logger.info('merge: canonical=%s заперт (merge_locked) — пропуск', canonical.pk)
        return
    transitivity_ok, reason = _passes_transitivity_guard(donor, canonical)
    if not transitivity_ok:
        write_audit(
            offer=None,
            decision=MergeAuditLog.Decision.REVIEW,
            actor=actor,
            score=score,
            signals={'rejected': reason, **(signals or {})},
            from_product=donor,
            to_product=canonical,
            run_id=run_id,
        )
        logger.info(
            'merge: transitivity guard отклонил donor=%s canonical=%s (%s)',
            donor.pk, canonical.pk, reason,
        )
        return

    donor_id = donor.pk
    canonical_id = canonical.pk

    with transaction.atomic():


        donor_offers = list(
            Offer.objects
            .filter(product=donor)
            .only('id', 'source', 'url')
        )
        canon_keys: set[tuple[str, str]] = set(
            Offer.objects
            .filter(product=canonical)
            .values_list('source', 'url')
        )
        for o in donor_offers:
            if (o.source, o.url) in canon_keys:
                logger.info(
                    'merge: удаляем дубликат оффера (source=%s, url=%s) у donor=%s',
                    o.source, o.url, donor_id,
                )
                o.delete()


        for rel in _one_to_many_fields():
            model: type[Model] = rel.related_model
            fk_name = rel.field.name
            _move_related(model, fk_name, donor, canonical)

        donor.delete()

    write_audit(
        offer=None, decision=MergeAuditLog.Decision.AUTO_MERGE,
        actor=actor, score=score, signals=signals or {},
        from_product=donor, to_product=canonical,
        run_id=run_id,
    )
    logger.info('merge: удалён donor id=%s в пользу canonical id=%s', donor_id, canonical_id)


def rollback_run(run_id: str) -> dict[str, int]:
    if not run_id:
        return {'reverted': 0, 'skipped': 0}

    audits = list(
        MergeAuditLog.objects
        .filter(run_id=run_id, reverted=False)
        .order_by('-created_at')
    )
    reverted = 0
    skipped = 0
    for a in audits:
        if a.decision != MergeAuditLog.Decision.AUTO_MERGE:
            skipped += 1
            continue
        if a.from_product_id is None or a.to_product_id is None:
            skipped += 1
            continue
        try:
            from_product = Product.objects.get(pk=a.from_product_id)
        except Product.DoesNotExist:
            logger.warning('rollback: from_product=%s удалён, пропуск', a.from_product_id)
            skipped += 1
            continue
        if a.offer_id is None:
            skipped += 1
            continue
        try:
            offer = Offer.objects.get(pk=a.offer_id)
        except Offer.DoesNotExist:
            skipped += 1
            continue
        with transaction.atomic():
            offer.product = from_product
            offer.save(update_fields=['product', 'updated_at'])
            a.reverted = True
            a.save(update_fields=['reverted', 'updated_at'])
        reverted += 1
    return {'reverted': reverted, 'skipped': skipped}


__all__ = ('apply_merge', 'rollback_run')
