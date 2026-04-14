"""Автоотчёты по аномалиям.

Генерирует текстовый и JSON-формат отчёта по обнаруженным аномалиям
за указанный период. Фильтрация по серьёзности и типу.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass

from django.utils import timezone

from apps.analytics.models import Anomaly


@dataclass
class ReportEntry:
    anomaly_id: int
    product_name: str
    product_id: int
    category: str
    anomaly_type: str
    anomaly_type_label: str
    severity: str
    severity_label: str
    detected_at: _dt.datetime
    description: str
    resolved: bool


def generate_report(
    days: int = 7,
    severity: str | None = None,
    anomaly_type: str | None = None,
    category_slug: str | None = None,
) -> list[ReportEntry]:
    since = timezone.now() - _dt.timedelta(days=days)
    qs = Anomaly.objects.filter(detected_at__gte=since).select_related('product__category')

    if severity:
        qs = qs.filter(severity=severity)
    if anomaly_type:
        qs = qs.filter(anomaly_type=anomaly_type)
    if category_slug:
        qs = qs.filter(product__category__slug=category_slug)

    qs = qs.order_by('-detected_at')

    entries: list[ReportEntry] = []
    type_labels = dict(Anomaly.AnomalyType.choices)
    sev_labels = dict(Anomaly.Severity.choices)

    for a in qs:
        entries.append(ReportEntry(
            anomaly_id=a.pk,
            product_name=a.product.name,
            product_id=a.product_id,
            category=a.product.category.name if a.product.category else '',
            anomaly_type=a.anomaly_type,
            anomaly_type_label=type_labels.get(a.anomaly_type, a.anomaly_type),
            severity=a.severity,
            severity_label=sev_labels.get(a.severity, a.severity),
            detected_at=a.detected_at,
            description=a.description,
            resolved=a.resolved,
        ))

    return entries


def report_to_text(entries: list[ReportEntry]) -> str:
    if not entries:
        return 'Аномалий не обнаружено за указанный период.'

    lines = [
        f'Отчёт по аномалиям ({len(entries)} шт.)',
        '=' * 60,
    ]
    for e in entries:
        status = '✓ разрешена' if e.resolved else '✗ активна'
        lines.append(
            f'\n[{e.severity_label.upper()}] {e.anomaly_type_label}'
            f'\n  Товар: {e.product_name} (id={e.product_id})'
            f'\n  Категория: {e.category}'
            f'\n  Дата: {e.detected_at:%Y-%m-%d %H:%M}'
            f'\n  Статус: {status}'
            f'\n  Описание: {e.description}'
        )
    lines.append('\n' + '=' * 60)

    by_type: dict[str, int] = {}
    by_sev: dict[str, int] = {}
    for e in entries:
        by_type[e.anomaly_type_label] = by_type.get(e.anomaly_type_label, 0) + 1
        by_sev[e.severity_label] = by_sev.get(e.severity_label, 0) + 1

    lines.append('Сводка:')
    lines.append('  По типу: ' + ', '.join(f'{k}: {v}' for k, v in by_type.items()))
    lines.append('  По серьёзности: ' + ', '.join(f'{k}: {v}' for k, v in by_sev.items()))
    active = sum(1 for e in entries if not e.resolved)
    lines.append(f'  Активных: {active}, разрешённых: {len(entries) - active}')

    return '\n'.join(lines)


def report_to_json(entries: list[ReportEntry]) -> str:
    data = {
        'generated_at': timezone.now().isoformat(),
        'total': len(entries),
        'anomalies': [
            {
                'id': e.anomaly_id,
                'product': e.product_name,
                'product_id': e.product_id,
                'category': e.category,
                'type': e.anomaly_type,
                'type_label': e.anomaly_type_label,
                'severity': e.severity,
                'severity_label': e.severity_label,
                'detected_at': e.detected_at.isoformat(),
                'description': e.description,
                'resolved': e.resolved,
            }
            for e in entries
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
