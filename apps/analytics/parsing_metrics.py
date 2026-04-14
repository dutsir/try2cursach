"""Метрики эффективности парсинга.

Подсчёт количества новых/обновлённых записей цен, товаров, ошибок
за указанный период. Выводится в виде простых счётчиков.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from apps.prices.models import PriceHistory
from apps.products.models import Category, Product


@dataclass
class ParsingStats:
    period_label: str
    total_price_records: int
    unique_products_updated: int
    total_products: int
    active_categories: int
    first_record: _dt.datetime | None
    last_record: _dt.datetime | None
    avg_records_per_product: float
    products_without_data: int


def compute_parsing_metrics(days: int = 7) -> ParsingStats:
    now = timezone.now()
    since = now - _dt.timedelta(days=days)

    recent_qs = PriceHistory.objects.filter(timestamp__gte=since)
    total_records = recent_qs.count()
    unique_products = recent_qs.values('product').distinct().count()

    total_products = Product.objects.filter(is_active=True).count()
    active_cats = Category.objects.filter(is_active=True).count()

    bounds = recent_qs.aggregate(first=Min('timestamp'), last=Max('timestamp'))

    all_product_ids = set(
        Product.objects.filter(is_active=True).values_list('id', flat=True)
    )
    products_with_data = set(
        PriceHistory.objects.values_list('product_id', flat=True).distinct()
    )
    no_data = len(all_product_ids - products_with_data)

    avg = total_records / unique_products if unique_products > 0 else 0.0

    return ParsingStats(
        period_label=f'Последние {days} дн.',
        total_price_records=total_records,
        unique_products_updated=unique_products,
        total_products=total_products,
        active_categories=active_cats,
        first_record=bounds['first'],
        last_record=bounds['last'],
        avg_records_per_product=round(avg, 1),
        products_without_data=no_data,
    )
