"""Кластеризация товаров по динамике цен.

Группирует товары в кластеры: волатильные, стабильные, лидеры падений,
лидеры роста. Использует KMeans по фичам динамики.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from apps.prices.models import PriceHistory
from apps.products.models import Product

logger = logging.getLogger(__name__)

CLUSTER_LABELS = {
    0: 'стабильные',
    1: 'волатильные',
    2: 'лидеры роста',
    3: 'лидеры падений',
}

MIN_RECORDS = 3


@dataclass
class ProductFeatures:
    product_id: int
    product_name: str
    category: str
    mean_price: float
    volatility: float      # std / mean (CV)
    trend: float           # (last - first) / first
    max_change_pct: float  # max single-step % change
    num_records: int


def _compute_features(product: Product) -> ProductFeatures | None:
    records = list(
        PriceHistory.objects
        .filter(product=product)
        .order_by('timestamp')
        .values_list('price', flat=True)
    )
    if len(records) < MIN_RECORDS:
        return None

    prices = np.array([float(p) for p in records], dtype=np.float64)
    mean_p = float(np.mean(prices))
    if mean_p == 0:
        return None

    volatility = float(np.std(prices) / mean_p)
    trend = float((prices[-1] - prices[0]) / prices[0]) if prices[0] != 0 else 0.0

    changes = np.abs(np.diff(prices))
    bases = prices[:-1]
    pct_changes = np.where(bases > 0, changes / bases, 0)
    max_change = float(np.max(pct_changes)) if len(pct_changes) else 0.0

    return ProductFeatures(
        product_id=product.pk,
        product_name=product.name,
        category=product.category.name if product.category else '',
        mean_price=mean_p,
        volatility=volatility,
        trend=trend,
        max_change_pct=max_change,
        num_records=len(records),
    )


def cluster_products(
    category_slug: str | None = None,
    n_clusters: int = 4,
) -> dict[str, list[ProductFeatures]]:
    """Возвращает {label: [ProductFeatures, ...]} после кластеризации."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    qs = Product.objects.filter(is_active=True).select_related('category')
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    features_list: list[ProductFeatures] = []
    for product in qs.iterator():
        f = _compute_features(product)
        if f is not None:
            features_list.append(f)

    if len(features_list) < n_clusters:
        logger.warning(
            'Недостаточно товаров для кластеризации (%d < %d)',
            len(features_list), n_clusters,
        )
        return {'все товары': features_list}

    X = np.array([
        [f.volatility, f.trend, f.max_change_pct]
        for f in features_list
    ])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    actual_k = min(n_clusters, len(features_list))
    km = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)

    cluster_means = {}
    for ci in range(actual_k):
        mask = labels == ci
        cluster_means[ci] = {
            'vol': float(np.mean(X[mask, 0])),
            'trend': float(np.mean(X[mask, 1])),
        }

    sorted_by_vol = sorted(cluster_means.items(), key=lambda kv: kv[1]['vol'])
    label_map: dict[int, str] = {}
    label_map[sorted_by_vol[0][0]] = 'стабильные'
    if actual_k >= 2:
        label_map[sorted_by_vol[-1][0]] = 'волатильные'
    for ci, stats in cluster_means.items():
        if ci in label_map:
            continue
        if stats['trend'] > 0.02:
            label_map[ci] = 'лидеры роста'
        elif stats['trend'] < -0.02:
            label_map[ci] = 'лидеры падений'
        else:
            label_map[ci] = f'кластер {ci}'

    result: dict[str, list[ProductFeatures]] = {}
    for idx, f in enumerate(features_list):
        lbl = label_map.get(labels[idx], f'кластер {labels[idx]}')
        result.setdefault(lbl, []).append(f)

    return result
