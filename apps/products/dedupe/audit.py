from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.utils import timezone

from ..models import MatchReview, MergeAuditLog, Offer, Product
from .features import Features

logger = logging.getLogger(__name__)


def write_audit(
    *,
    offer: Offer | None,
    decision: str,
    actor: str = MergeAuditLog.Actor.AUTO,
    score: float = 0.0,
    signals: dict[str, Any] | None = None,
    from_product: Product | None = None,
    to_product: Product | None = None,
    run_id: str = '',
) -> MergeAuditLog:
    return MergeAuditLog.objects.create(
        offer=offer,
        from_product=from_product,
        to_product=to_product,
        actor=actor,
        decision=decision,
        score=Decimal(str(round(min(max(score, 0.0), 1.0), 3))),
        signals=signals or {},
        run_id=run_id or '',
    )


def enqueue_review(
    *,
    offer: Offer,
    suggested: Product,
    score: float,
    signals: dict[str, Any] | None = None,
) -> MatchReview | None:
    if offer is None or suggested is None or offer.pk == getattr(suggested, 'pk', None):
        return None
    obj, created = MatchReview.objects.get_or_create(
        offer=offer,
        suggested_product=suggested,
        defaults={
            'score': Decimal(str(round(score, 3))),
            'signals': signals or {},
            'status': MatchReview.Status.PENDING,
        },
    )
    if created:
        return obj
    if obj.status == MatchReview.Status.PENDING:
        obj.score = Decimal(str(round(score, 3)))
        obj.signals = signals or {}
        obj.save(update_fields=['score', 'signals', 'updated_at'])
    return obj


def approve_review(review: MatchReview, *, user: Any | None = None) -> None:
    if review.status != MatchReview.Status.PENDING:
        return
    offer = review.offer
    target = review.suggested_product
    prev_product = offer.product

    offer.product = target
    offer.save(update_fields=['product', 'updated_at'])

    write_audit(
        offer=offer,
        decision=MergeAuditLog.Decision.AUTO_MERGE,
        actor=MergeAuditLog.Actor.MANUAL,
        score=float(review.score),
        signals={'review_id': review.pk, **(review.signals or {})},
        from_product=prev_product,
        to_product=target,
    )

    review.status = MatchReview.Status.APPROVED
    review.decided_at = timezone.now()
    if user is not None:
        review.decided_by = user
    review.save(update_fields=['status', 'decided_at', 'decided_by', 'updated_at'])


def reject_review(review: MatchReview, *, user: Any | None = None, note: str = '') -> None:
    if review.status != MatchReview.Status.PENDING:
        return
    review.status = MatchReview.Status.REJECTED
    review.decided_at = timezone.now()
    if user is not None:
        review.decided_by = user
    if note:
        review.note = note[:512]
    review.save(update_fields=['status', 'decided_at', 'decided_by', 'note', 'updated_at'])


__all__ = ('approve_review', 'enqueue_review', 'reject_review', 'write_audit')
