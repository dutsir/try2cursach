"""Сохранение агрегированной аналитики в БД (модель AnalyticsSnapshot).

Сырые ряды — в PriceHistory / Anomaly / PriceForecast / CurrencyRate.
Снимки — для дашборда и сравнения «как было вчера / неделю назад».
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from django.db.models import Count
from django.utils import timezone

from apps.analytics.models import AnalyticsSnapshot, Anomaly, CurrencyRate


def _json_safe(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (_dt.datetime, _dt.date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    return obj


def build_full_dashboard_payload(
    *,
    period_days: int = 7,
    metrics_days: int = 7,
    deals_days: int = 30,
    heatmap_days: int = 7,
    heatmap_max_products: int = 30,
    deals_limit: int = 50,
    sensitivity_limit: int = 30,
    n_clusters: int = 4,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Возвращает (summary, payload) для kind=full_dashboard."""
    from apps.analytics.best_deals import find_best_deals
    from apps.analytics.clustering import ProductFeatures, cluster_products
    from apps.analytics.currency_sensitivity import analyze_category_sensitivity
    from apps.analytics.heatmap import build_heatmap
    from apps.analytics.parsing_metrics import compute_parsing_metrics
    from apps.analytics.price_index import compute_category_index

    metrics = compute_parsing_metrics(days=metrics_days)
    indices = compute_category_index(period_days=period_days)
    deals = find_best_deals(
        days=deals_days, category_slug=None, limit=deals_limit,
    )
    clusters = cluster_products(category_slug=None, n_clusters=n_clusters)
    dates, heat_rows = build_heatmap(
        category_slug=None, days=heatmap_days, max_products=heatmap_max_products,
    )
    sens = analyze_category_sensitivity(
        category_slug=None, currency_code='USD', limit=sensitivity_limit,
    )

    since = timezone.now() - _dt.timedelta(days=period_days)
    an_qs = Anomaly.objects.filter(detected_at__gte=since)
    anomaly_total = an_qs.count()
    by_severity = dict(
        an_qs.values('severity').annotate(c=Count('id')).values_list('severity', 'c')
    )
    by_type = dict(
        an_qs.values('anomaly_type').annotate(c=Count('id')).values_list('anomaly_type', 'c')
    )

    latest_rates = list(
        CurrencyRate.objects.order_by('-date', 'currency_code')[:9]
    )
    rates_summary = [
        {'currency': r.currency_code, 'rate': float(r.rate), 'date': r.date.isoformat()}
        for r in latest_rates
    ]

    summary = {
        'metrics_days': metrics_days,
        'period_days': period_days,
        'total_price_records_window': metrics.total_price_records,
        'unique_products_updated_window': metrics.unique_products_updated,
        'total_active_products': metrics.total_products,
        'categories_count': metrics.active_categories,
        'products_without_prices': metrics.products_without_data,
        'anomalies_in_period': anomaly_total,
        'anomalies_by_severity': by_severity,
        'anomalies_by_type': by_type,
        'category_index_rows': len(indices),
        'deals_listed': len(deals),
        'cluster_labels': {k: len(v) for k, v in clusters.items()},
        'heatmap_products': len(heat_rows),
        'heatmap_dates': len(dates),
        'sensitivity_rows': len(sens),
    }

    def feat_to_dict(f: ProductFeatures) -> dict[str, Any]:
        return {
            'product_id': f.product_id,
            'product_name': f.product_name,
            'category': f.category,
            'mean_price': f.mean_price,
            'volatility': f.volatility,
            'trend': f.trend,
            'max_change_pct': f.max_change_pct,
            'num_records': f.num_records,
        }

    clusters_payload = {
        label: [feat_to_dict(x) for x in items[:200]]
        for label, items in clusters.items()
    }

    payload = {
        'generated_at': timezone.now().isoformat(),
        'parsing_metrics': _json_safe(asdict(metrics)),
        'category_index': [_json_safe(asdict(x)) for x in indices],
        'deals_top': [_json_safe(asdict(d)) for d in deals],
        'clusters': clusters_payload,
        'heatmap': {
            'dates': [d.isoformat() for d in dates],
            'rows': [
                {
                    'product_id': r.product_id,
                    'product_name': r.product_name,
                    'cells': [
                        {
                            'date': c.date.isoformat(),
                            'price': c.price,
                            'change_pct': c.change_pct,
                            'indicator': c.indicator,
                        }
                        for c in r.cells
                    ],
                }
                for r in heat_rows
            ],
        },
        'sensitivity_usd': [
            {
                'product_id': r.product_id,
                'product_name': r.product_name,
                'correlation': r.correlation,
                'p_value': r.p_value,
                'sample_size': r.sample_size,
                'conclusion': r.conclusion,
                'detail': r.detail,
            }
            for r in sens
        ],
        'anomalies_summary': {
            'period_days': period_days,
            'total': anomaly_total,
            'by_severity': by_severity,
            'by_type': by_type,
        },
        'currency_rates_latest': rates_summary,
    }

    return summary, payload


def save_full_dashboard_snapshot(**kwargs: Any) -> AnalyticsSnapshot:
    """Считает полный дашборд и пишет одну строку AnalyticsSnapshot."""
    summary, payload = build_full_dashboard_payload(**kwargs)
    params = {k: v for k, v in kwargs.items() if v is not None}
    return AnalyticsSnapshot.objects.create(
        kind=AnalyticsSnapshot.Kind.FULL_DASHBOARD,
        scope_key='',
        parameters=params,
        summary=summary,
        payload=payload,
    )


def save_kind_snapshot(
    kind: str,
    *,
    scope_key: str = '',
    parameters: dict[str, Any] | None = None,
) -> AnalyticsSnapshot:
    """Сохраняет один тип отчёта (без полного дашборда)."""
    parameters = parameters or {}
    if kind == AnalyticsSnapshot.Kind.CLUSTERS:
        from apps.analytics.clustering import cluster_products

        clusters = cluster_products(
            category_slug=parameters.get('category') or None,
            n_clusters=int(parameters.get('clusters', 4)),
        )
        summary = {label: len(items) for label, items in clusters.items()}
        payload = {
            label: [
                {
                    'product_id': f.product_id,
                    'product_name': f.product_name,
                    'mean_price': f.mean_price,
                    'volatility': f.volatility,
                    'trend': f.trend,
                }
                for f in items[:500]
            ]
            for label, items in clusters.items()
        }
    elif kind == AnalyticsSnapshot.Kind.CATEGORY_INDEX:
        from apps.analytics.price_index import compute_category_index

        period = int(parameters.get('period', 7))
        indices = compute_category_index(period_days=period)
        summary = {'rows': len(indices)}
        payload = [asdict(x) for x in indices]
    elif kind == AnalyticsSnapshot.Kind.PARSING_METRICS:
        from apps.analytics.parsing_metrics import compute_parsing_metrics

        days = int(parameters.get('days', 7))
        s = compute_parsing_metrics(days=days)
        summary = {'total_price_records': s.total_price_records, 'unique_products': s.unique_products_updated}
        payload = _json_safe(asdict(s))
    elif kind == AnalyticsSnapshot.Kind.DEALS_TOP:
        from apps.analytics.best_deals import find_best_deals

        deals = find_best_deals(
            days=int(parameters.get('days', 30)),
            category_slug=parameters.get('category'),
            limit=int(parameters.get('limit', 50)),
        )
        summary = {'count': len(deals)}
        payload = [_json_safe(asdict(d)) for d in deals]
    elif kind == AnalyticsSnapshot.Kind.ANOMALIES_SUMMARY:
        days = int(parameters.get('days', 7))
        since = timezone.now() - _dt.timedelta(days=days)
        qs = Anomaly.objects.filter(detected_at__gte=since)
        total = qs.count()
        by_severity = dict(qs.values('severity').annotate(c=Count('id')).values_list('severity', 'c'))
        by_type = dict(qs.values('anomaly_type').annotate(c=Count('id')).values_list('anomaly_type', 'c'))
        summary = {'total': total, 'days': days}
        payload = {'by_severity': by_severity, 'by_type': by_type, 'days': days}
    else:
        raise ValueError(f'Неизвестный kind: {kind}')

    return AnalyticsSnapshot.objects.create(
        kind=kind,
        scope_key=scope_key,
        parameters=parameters,
        summary=summary,
        payload=payload if isinstance(payload, dict) else {'data': payload},
    )
