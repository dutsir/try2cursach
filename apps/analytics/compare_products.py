"""Сравнение двух и более товаров в табличной форме.

Сводка: текущая цена, мин/макс/средняя за период, тренд, прогноз (если есть).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, Max, Min
from django.utils import timezone

from apps.prices.models import PriceHistory
from apps.products.models import Product
from .models import PriceForecast


@dataclass
class ProductSummary:
    product_id: int
    name: str
    category: str
    url: str
    current_price: Decimal | None
    min_price_30d: Decimal | None
    max_price_30d: Decimal | None
    avg_price_30d: float | None
    change_30d_pct: float | None
    records_count: int
    forecast_7d: Decimal | None
    forecast_direction: str


def compare(product_ids: list[int], days: int = 30) -> list[ProductSummary]:
    """Сводка по нескольким товарам для сравнения."""
    since = timezone.now() - _dt.timedelta(days=days)
    results: list[ProductSummary] = []

    for pid in product_ids:
        try:
            product = Product.objects.select_related('category').get(pk=pid)
        except Product.DoesNotExist:
            continue

        records = list(
            PriceHistory.objects
            .filter(product=product, timestamp__gte=since)
            .order_by('timestamp')
            .values('price', 'timestamp')
        )

        current = None
        actual = (
            PriceHistory.objects
            .filter(product=product, is_actual=True)
            .order_by('-timestamp')
            .first()
        )
        if actual:
            current = actual.price

        stats = (
            PriceHistory.objects
            .filter(product=product, timestamp__gte=since)
            .aggregate(
                min_p=Min('price'),
                max_p=Max('price'),
                avg_p=Avg('price'),
            )
        )

        change_pct = None
        if records and len(records) >= 2:
            first_p = float(records[0]['price'])
            last_p = float(records[-1]['price'])
            if first_p > 0:
                change_pct = round((last_p - first_p) / first_p * 100, 1)

        forecast_obj = (
            PriceForecast.objects
            .filter(product=product, method='ARIMA')
            .order_by('forecast_date')
            .first()
        )
        forecast_price = forecast_obj.predicted_price if forecast_obj else None

        direction = ''
        if forecast_price and current:
            if forecast_price > current:
                direction = 'рост'
            elif forecast_price < current:
                direction = 'снижение'
            else:
                direction = 'стабильно'

        results.append(ProductSummary(
            product_id=product.pk,
            name=product.name,
            category=product.category.name if product.category else '',
            url=product.url or '',
            current_price=current,
            min_price_30d=stats['min_p'],
            max_price_30d=stats['max_p'],
            avg_price_30d=round(float(stats['avg_p']), 2) if stats['avg_p'] else None,
            change_30d_pct=change_pct,
            records_count=len(records),
            forecast_7d=forecast_price,
            forecast_direction=direction,
        ))

    return results
