"""Безопасное слияние двух мастер-Products в один canonical.

Используется и разовой командой (link_cross_source), и (в перспективе) матчером
при парсинге. Переносит ВСЕ связанные объекты с дубля на canonical, аккуратно
разруливая unique-коллизии, после чего удаляет дубль.

Инвариант same-source сохраняется: если у дубля есть оффер источника, который
уже представлен у canonical (и источник не из WITHIN_SOURCE_DEDUP_SOURCES), слияние
ОТКЛОНЯЕТСЯ — иначе на одном мастере окажутся два оффера одного non-WB источника,
ровно та склейка, которую мы запрещаем (см. [[dedup-principle]]).
"""
from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from .matcher import WITHIN_SOURCE_DEDUP_SOURCES
from ..models import MatchReview, MergeAuditLog, Offer, Product

logger = logging.getLogger(__name__)


def _sources_collide(canonical: Product, dup: Product) -> set[str]:
    """Источники, представленные И у canonical, И у дубля (кроме WB-семейства).

    Непустой результат означает, что слияние создало бы запрещённую
    внутри-источниковую склейку.
    """
    canon_src = set(
        Offer.objects.filter(product=canonical)
        .values_list('source', flat=True).distinct(),
    )
    dup_src = set(
        Offer.objects.filter(product=dup)
        .values_list('source', flat=True).distinct(),
    )
    overlap = {
        s for s in (canon_src & dup_src)
        if s and s.lower() not in WITHIN_SOURCE_DEDUP_SOURCES
    }
    return overlap


def can_merge(
    canonical: Product, dup: Product, *, allow_same_source: bool = False,
) -> tuple[bool, str]:
    """Проверка предусловий слияния (без изменения БД).

    allow_same_source: ЯВНЫЙ обход инварианта same-source. По умолчанию False —
    cross-source путь (find_master, link_cross_source) НЕ должен сливать два non-WB
    оффера одного источника. True используется ТОЛЬКО осознанно — командой схлопывания
    within-source дублей по идентичному имени (разрешено владельцем поверх
    [[dedup-principle]]: «копии хуже, чем нарушение принципа»).
    """
    if canonical.pk == dup.pk:
        return False, 'same_product'
    if canonical.category_id != dup.category_id:
        return False, 'category_mismatch'
    if getattr(canonical, 'merge_locked', False) or getattr(dup, 'merge_locked', False):
        return False, 'merge_locked'
    if not allow_same_source:
        overlap = _sources_collide(canonical, dup)
        if overlap:
            return False, f'same_source_overlap:{",".join(sorted(overlap))}'
    return True, 'ok'


def _repoint_unique_together(
    model: Any, dup: Product, canonical: Product, *,
    peer_field: str, product_field: str = 'product',
) -> int:
    """Переносит строки модели с unique_together=(peer_field, product_field).

    product_field — имя FK на Product (у MatchReview это 'suggested_product').
    Строки дубля, чей peer уже имеет строку у canonical, удаляются (иначе
    нарушим unique-constraint). Остальные перенацеливаются на canonical.
    """
    existing_peers = set(
        model.objects.filter(**{product_field: canonical})
        .values_list(peer_field, flat=True),
    )
    dup_rows = model.objects.filter(**{product_field: dup})
    colliding = dup_rows.filter(**{f'{peer_field}__in': existing_peers})
    deleted = colliding.count()
    colliding.delete()
    moved = dup_rows.update(**{product_field: canonical})
    if deleted:
        logger.debug(
            '%s: удалено %d коллизий, перенесено %d на canonical=%s',
            model.__name__, deleted, moved, canonical.pk,
        )
    return moved


@transaction.atomic
def merge_products(
    canonical_id: int, dup_id: int, *,
    actor: str = MergeAuditLog.Actor.AUTO,
    decision: str = MergeAuditLog.Decision.AUTO_MERGE,
    score: float = 0.0,
    signals: dict[str, Any] | None = None,
    run_id: str = '',
    allow_same_source: bool = False,
) -> dict[str, Any]:
    """Сливает dup в canonical. Возвращает stats (merged: bool, ...).

    Перед вызовом НЕ требуется блокировка — берётся select_for_update внутри.
    allow_same_source — см. can_merge (осознанный обход для within-source схлопывания).
    """
    ids = sorted({canonical_id, dup_id})
    locked = {
        p.pk: p
        for p in Product.objects.select_for_update().filter(pk__in=ids)
    }
    canonical = locked.get(canonical_id)
    dup = locked.get(dup_id)
    if canonical is None or dup is None:
        return {'merged': False, 'reason': 'not_found'}

    ok, reason = can_merge(canonical, dup, allow_same_source=allow_same_source)
    if not ok:
        return {'merged': False, 'reason': reason}

    from apps.prices.models import PriceHistory
    from apps.alerts.models import Notification, Subscription, WishlistItem
    from apps.builds.models import BuildItem

    stats: dict[str, Any] = {'merged': True, 'reason': 'ok'}

    # Простые repoint (нет product-уникальности или SET_NULL).
    stats['offers'] = Offer.objects.filter(product=dup).update(product=canonical)
    stats['price_history'] = PriceHistory.objects.filter(product=dup).update(product=canonical)
    stats['notifications'] = Notification.objects.filter(product=dup).update(product=canonical)
    stats['build_items'] = BuildItem.objects.filter(product=dup).update(product=canonical)
    MergeAuditLog.objects.filter(from_product=dup).update(from_product=canonical)
    MergeAuditLog.objects.filter(to_product=dup).update(to_product=canonical)

    # repoint с unique_together — разруливаем коллизии.
    stats['subscriptions'] = _repoint_unique_together(
        Subscription, dup, canonical, peer_field='user',
    )
    stats['wishlist_items'] = _repoint_unique_together(
        WishlistItem, dup, canonical, peer_field='wishlist',
    )
    # MatchReview: unique (offer, suggested_product) — peer=offer, product=suggested_product.
    stats['match_reviews'] = _repoint_unique_together(
        MatchReview, dup, canonical,
        peer_field='offer', product_field='suggested_product',
    )

    MergeAuditLog.objects.create(
        from_product=canonical, to_product=canonical,
        actor=actor, decision=decision, score=score,
        signals={**(signals or {}), 'merged_dup_id': dup_id},
        run_id=run_id,
    )

    dup.delete()
    stats['dup_deleted'] = dup_id
    stats['canonical'] = canonical_id
    return stats
