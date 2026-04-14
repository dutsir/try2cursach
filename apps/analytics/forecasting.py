"""Прогноз цен с использованием ARIMA (statsmodels).

Для каждого товара строит прогноз на horizon дней с доверительными
интервалами и сохраняет результаты в PriceForecast.
"""
from __future__ import annotations

import datetime as _dt
import logging
from decimal import Decimal

import numpy as np

from apps.prices.models import PriceHistory
from apps.products.models import Product
from .models import PriceForecast

logger = logging.getLogger(__name__)

MIN_HISTORY = 7


def forecast_product(
    product: Product,
    horizon: int = 7,
    order: tuple[int, int, int] = (1, 1, 1),
) -> list[PriceForecast]:
    """ARIMA-прогноз для товара. Возвращает список созданных PriceForecast."""
    from statsmodels.tsa.arima.model import ARIMA

    records = list(
        PriceHistory.objects
        .filter(product=product)
        .order_by('timestamp')
        .values('timestamp', 'price')
    )
    if len(records) < MIN_HISTORY:
        logger.debug(
            'Недостаточно данных для прогноза %s (%d < %d)',
            product.name, len(records), MIN_HISTORY,
        )
        return []

    prices = np.array([float(r['price']) for r in records], dtype=np.float64)
    last_date = records[-1]['timestamp'].date()

    try:
        model = ARIMA(prices, order=order)
        fit = model.fit()
        fc = fit.get_forecast(steps=horizon)
        mean = fc.predicted_mean
        ci = fc.conf_int(alpha=0.1)
    except Exception:
        logger.warning('ARIMA не сошёлся для %s, пробуем (1,0,0)', product.name)
        try:
            model = ARIMA(prices, order=(1, 0, 0))
            fit = model.fit()
            fc = fit.get_forecast(steps=horizon)
            mean = fc.predicted_mean
            ci = fc.conf_int(alpha=0.1)
        except Exception:
            logger.error('ARIMA не удался для %s', product.name, exc_info=True)
            return []

    created: list[PriceForecast] = []
    for i in range(horizon):
        fdate = last_date + _dt.timedelta(days=i + 1)
        pred = max(float(mean[i]), 0)
        low = max(float(ci[i, 0]), 0) if ci.shape[1] >= 2 else None
        high = max(float(ci[i, 1]), 0) if ci.shape[1] >= 2 else None

        obj, _ = PriceForecast.objects.update_or_create(
            product=product,
            forecast_date=fdate,
            method='ARIMA',
            defaults={
                'predicted_price': Decimal(str(round(pred, 2))),
                'lower_bound': Decimal(str(round(low, 2))) if low is not None else None,
                'upper_bound': Decimal(str(round(high, 2))) if high is not None else None,
            },
        )
        created.append(obj)

    logger.info(
        'Прогноз для %s: %d дней, последняя цена %.0f₽, прогноз %.0f₽',
        product.name, horizon, prices[-1], float(mean[0]),
    )
    return created


def forecast_all(
    category_slug: str | None = None,
    horizon: int = 7,
    limit: int | None = None,
) -> dict:
    qs = Product.objects.filter(is_active=True)
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    qs = qs.order_by('id')
    if limit:
        qs = qs[:limit]

    total = 0
    errors = 0
    for product in qs:
        try:
            forecasts = forecast_product(product, horizon=horizon)
            total += len(forecasts)
        except Exception:
            errors += 1
            logger.error('Ошибка прогноза для %s', product.name, exc_info=True)

    return {'forecasts_created': total, 'errors': errors}


def forecast_for_product_ids(
    product_ids: list[int],
    horizon: int = 7,
) -> dict:
    """Прогноз только для указанных товаров (после ручного парсинга)."""
    if not product_ids:
        return {'forecasts_created': 0, 'errors': 0}

    total = 0
    errors = 0
    for pid in product_ids:
        try:
            product = Product.objects.get(pk=pid, is_active=True)
        except Product.DoesNotExist:
            continue
        try:
            forecasts = forecast_product(product, horizon=horizon)
            total += len(forecasts)
        except Exception:
            errors += 1
            logger.error('Ошибка прогноза для product_id=%s', pid, exc_info=True)

    return {'forecasts_created': total, 'errors': errors}
