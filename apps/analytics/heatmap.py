"""Тепловая карта ценовых изменений (текстовая таблица).

Сетка товаров × даты: процент изменения цены за день/неделю
с текстовой цветовой индикацией (▲ ▼ ●).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone

from apps.prices.models import PriceHistory
from apps.products.models import Category, Product


@dataclass
class HeatmapCell:
    date: _dt.date
    price: float | None
    change_pct: float | None  # к предыдущему периоду

    @property
    def indicator(self) -> str:
        if self.change_pct is None or self.price is None:
            return '  -  '
        if self.change_pct > 5:
            return f'▲▲{self.change_pct:+.0f}%'
        if self.change_pct > 0.5:
            return f' ▲{self.change_pct:+.0f}%'
        if self.change_pct < -5:
            return f'▼▼{self.change_pct:+.0f}%'
        if self.change_pct < -0.5:
            return f' ▼{self.change_pct:+.0f}%'
        return f'  ●{self.change_pct:+.0f}%'


@dataclass
class HeatmapRow:
    product_name: str
    product_id: int
    cells: list[HeatmapCell]


def build_heatmap(
    category_slug: str | None = None,
    days: int = 7,
    max_products: int = 30,
) -> tuple[list[_dt.date], list[HeatmapRow]]:
    """Строит тепловую карту за последние `days` дней.

    Returns (dates, rows) — список дат-колонок и строки товаров.
    """
    now = timezone.now()
    start = now - _dt.timedelta(days=days)

    dates = []
    d = start.date()
    while d <= now.date():
        dates.append(d)
        d += _dt.timedelta(days=1)

    qs = Product.objects.filter(is_active=True).select_related('category')
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    products = list(qs.order_by('name')[:max_products])

    rows: list[HeatmapRow] = []
    for product in products:
        records = list(
            PriceHistory.objects
            .filter(product=product, timestamp__gte=start)
            .order_by('timestamp')
            .values('price', 'timestamp')
        )
        if not records:
            continue

        price_by_date: dict[_dt.date, float] = {}
        for r in records:
            price_by_date[r['timestamp'].date()] = float(r['price'])

        cells: list[HeatmapCell] = []
        prev_price: float | None = None
        for dt in dates:
            price = price_by_date.get(dt)
            change: float | None = None
            if price is not None and prev_price is not None and prev_price > 0:
                change = (price - prev_price) / prev_price * 100
            cells.append(HeatmapCell(date=dt, price=price, change_pct=change))
            if price is not None:
                prev_price = price

        rows.append(HeatmapRow(product_name=product.name, product_id=product.pk, cells=cells))

    return dates, rows
