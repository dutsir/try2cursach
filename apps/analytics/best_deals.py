"""Самые выгодные товары — товары, достигшие минимума за N дней.

Сравнивает текущую (актуальную) цену с минимальной и средней за период.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, Min
from django.utils import timezone

from apps.prices.models import PriceHistory
from apps.products.models import Product


@dataclass
class DealInfo:
    product_id: int
    product_name: str
    category: str
    current_price: Decimal
    min_price: Decimal
    avg_price: float
    discount_from_avg_pct: float
    is_at_minimum: bool
    url: str


def find_best_deals(
    days: int = 30,
    category_slug: str | None = None,
    limit: int = 20,
) -> list[DealInfo]:
    """Находит товары с наибольшей скидкой относительно средней цены за period."""
    since = timezone.now() - _dt.timedelta(days=days)

    qs = Product.objects.filter(is_active=True).select_related('category')
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    deals: list[DealInfo] = []

    for product in qs.iterator():
        actual = (
            PriceHistory.objects
            .filter(product=product, is_actual=True)
            .order_by('-timestamp')
            .first()
        )
        if not actual:
            continue

        stats = (
            PriceHistory.objects
            .filter(product=product, timestamp__gte=since)
            .aggregate(min_price=Min('price'), avg_price=Avg('price'))
        )
        min_p = stats['min_price']
        avg_p = stats['avg_price']
        if not min_p or not avg_p or avg_p == 0:
            continue

        current = actual.price
        discount_pct = float((float(avg_p) - float(current)) / float(avg_p) * 100)

        deals.append(DealInfo(
            product_id=product.pk,
            product_name=product.name,
            category=product.category.name if product.category else '',
            current_price=current,
            min_price=min_p,
            avg_price=round(float(avg_p), 2),
            discount_from_avg_pct=round(discount_pct, 1),
            is_at_minimum=(current <= min_p),
            url=product.url or '',
        ))

    deals.sort(key=lambda d: -d.discount_from_avg_pct)
    return deals[:limit]
