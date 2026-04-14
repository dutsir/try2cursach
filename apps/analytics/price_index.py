"""Индекс цен по категориям.

Средняя и медианная цена по категории в динамике, сравнение текущего
периода с предыдущим.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from django.db.models import Avg, Count
from django.utils import timezone

from apps.prices.models import PriceHistory
from apps.products.models import Category


@dataclass
class CategoryIndex:
    category_name: str
    category_slug: str
    current_mean: float
    current_median: float
    prev_mean: float | None
    prev_median: float | None
    mean_change_pct: float | None
    median_change_pct: float | None
    product_count: int


def _median(values: list[float]) -> float:
    return float(np.median(values)) if values else 0.0


def compute_category_index(
    period_days: int = 7,
) -> list[CategoryIndex]:
    """Вычисляет индекс цен для каждой активной категории.

    current = актуальные цены (is_actual=True)
    prev = цены от period_days..2*period_days назад
    """
    now = timezone.now()
    prev_start = now - _dt.timedelta(days=period_days * 2)
    prev_end = now - _dt.timedelta(days=period_days)

    results: list[CategoryIndex] = []

    for cat in Category.objects.filter(is_active=True).order_by('name'):
        current_prices = list(
            PriceHistory.objects
            .filter(product__category=cat, is_actual=True)
            .values_list('price', flat=True)
        )
        if not current_prices:
            continue

        curr_floats = [float(p) for p in current_prices]
        current_mean = float(np.mean(curr_floats))
        current_median = _median(curr_floats)

        prev_prices = list(
            PriceHistory.objects
            .filter(
                product__category=cat,
                timestamp__gte=prev_start,
                timestamp__lt=prev_end,
            )
            .values_list('price', flat=True)
        )

        prev_mean: float | None = None
        prev_median: float | None = None
        mean_change: float | None = None
        median_change: float | None = None

        if prev_prices:
            prev_floats = [float(p) for p in prev_prices]
            prev_mean = float(np.mean(prev_floats))
            prev_median = _median(prev_floats)
            if prev_mean > 0:
                mean_change = (current_mean - prev_mean) / prev_mean * 100
            if prev_median > 0:
                median_change = (current_median - prev_median) / prev_median * 100

        results.append(CategoryIndex(
            category_name=cat.name,
            category_slug=cat.slug,
            current_mean=current_mean,
            current_median=current_median,
            prev_mean=prev_mean,
            prev_median=prev_median,
            mean_change_pct=mean_change,
            median_change_pct=median_change,
            product_count=len(current_prices),
        ))

    return results
