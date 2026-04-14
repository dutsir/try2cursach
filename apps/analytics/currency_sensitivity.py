"""Анализ чувствительности цен товаров к курсу валют.

Вычисляет корреляцию Пирсона между ценой товара и курсом валюты ЦБ РФ.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from scipy.stats import pearsonr

from apps.prices.models import PriceHistory
from apps.products.models import Product
from .models import CurrencyRate

logger = logging.getLogger(__name__)

MIN_POINTS = 5


@dataclass
class SensitivityResult:
    product_id: int
    product_name: str
    currency: str
    correlation: float
    p_value: float
    sample_size: int
    conclusion: str
    detail: str


def _conclusion_text(corr: float) -> str:
    abs_c = abs(corr)
    if abs_c > 0.7:
        strength = 'Сильная'
    elif abs_c > 0.4:
        strength = 'Умеренная'
    elif abs_c > 0.2:
        strength = 'Слабая'
    else:
        return 'Зависимости не выявлено'
    direction = 'прямая' if corr > 0 else 'обратная'
    return f'{strength} {direction} зависимость'


def analyze_product_sensitivity(
    product: Product,
    currency_code: str = 'USD',
) -> SensitivityResult | None:
    """Корреляция цены товара с курсом валюты по совпадающим датам."""
    price_records = list(
        PriceHistory.objects
        .filter(product=product)
        .order_by('timestamp')
        .values('timestamp', 'price')
    )
    if len(price_records) < MIN_POINTS:
        return None

    price_by_date: dict = {}
    for r in price_records:
        d = r['timestamp'].date()
        price_by_date[d] = float(r['price'])

    rate_records = dict(
        CurrencyRate.objects
        .filter(currency_code=currency_code)
        .values_list('date', 'rate')
    )

    common_dates = sorted(set(price_by_date) & set(rate_records))
    if len(common_dates) < MIN_POINTS:
        return None

    prices = np.array([price_by_date[d] for d in common_dates])
    rates = np.array([float(rate_records[d]) for d in common_dates])

    corr, p_val = pearsonr(prices, rates)

    conclusion = _conclusion_text(corr)
    detail = (
        f'Корреляция Пирсона: {corr:.3f} (p={p_val:.4f}). '
        f'Период: {common_dates[0]:%d.%m.%Y}–{common_dates[-1]:%d.%m.%Y}, '
        f'{len(common_dates)} совпадающих дат. '
        f'{conclusion}: при росте {currency_code} цена товара '
        f'{"растёт" if corr > 0 else "снижается"}.'
    )

    return SensitivityResult(
        product_id=product.pk,
        product_name=product.name,
        currency=currency_code,
        correlation=float(corr),
        p_value=float(p_val),
        sample_size=len(common_dates),
        conclusion=conclusion,
        detail=detail,
    )


def analyze_category_sensitivity(
    category_slug: str | None = None,
    currency_code: str = 'USD',
    limit: int = 50,
) -> list[SensitivityResult]:
    """Корреляция для товаров категории (или всех). Сортировка по |corr| desc."""
    qs = Product.objects.filter(is_active=True)
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    results: list[SensitivityResult] = []
    for product in qs.order_by('id')[:limit]:
        r = analyze_product_sensitivity(product, currency_code)
        if r is not None:
            results.append(r)

    results.sort(key=lambda x: -abs(x.correlation))
    return results
