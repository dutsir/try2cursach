from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from django.utils import timezone

from apps.products.models import Product

from .models import PriceHistory


PRICE_DROP_THRESHOLD = 0.10

AVG_WINDOW_DAYS = 30
SHORT_WINDOW_DAYS = 7


@dataclass
class PriceStats:

    current: int | None
    min_price: int | None
    min_date: date | None
    max_price: int | None
    max_date: date | None
    avg_30d: int | None

    # 7-дневное окно (зеркало "за всё время")
    min_price_7d: int | None
    min_date_7d: date | None
    max_price_7d: int | None
    max_date_7d: date | None
    avg_7d: int | None
    points_7d: int

    # 30-дневное окно: min/max/даты (avg_30d уже есть выше)
    min_price_30d: int | None
    min_date_30d: date | None
    max_price_30d: int | None
    max_date_30d: date | None
    points_30d: int

    delta_7d_pct: float | None
    delta_30d_pct: float | None

    is_min_30d: bool
    is_min_all_time: bool
    drop_alert: bool
    drop_alert_pct: float | None

    history_points: int


def _daily_min_series(
    history: Iterable[PriceHistory],
) -> list[tuple[date, int]]:
    by_day: dict[date, int] = {}
    for ph in history:
        if ph.price <= 0:
            continue
        d = timezone.localtime(ph.timestamp).date()
        cur = by_day.get(d)
        if cur is None or ph.price < cur:
            by_day[d] = int(ph.price)
    return sorted(by_day.items(), key=lambda x: x[0])


def _avg_for_window(
    daily: list[tuple[date, int]],
    *,
    end: date,
    days: int,
) -> int | None:
    if not daily or days <= 0:
        return None
    start = end - timedelta(days=days - 1)
    prices = [p for d, p in daily if start <= d <= end]
    if not prices:
        return None
    return int(round(sum(prices) / len(prices)))


def _window_aggregates(
    daily: list[tuple[date, int]],
    *,
    end: date,
    days: int,
) -> tuple[int | None, date | None, int | None, date | None, int | None, int]:
    """Зеркало логики «за всё время», но на срезе [end-days+1 .. end].

    Возвращает (min_price, min_date, max_price, max_date, avg, points_count).
    Если в окне нет точек — все агрегаты None, points = 0.
    """
    if not daily or days <= 0:
        return None, None, None, None, None, 0
    start = end - timedelta(days=days - 1)
    points = [(d, p) for d, p in daily if start <= d <= end]
    if not points:
        return None, None, None, None, None, 0
    min_d, min_p = min(points, key=lambda x: x[1])
    max_d, max_p = max(points, key=lambda x: x[1])
    avg = int(round(sum(p for _, p in points) / len(points)))
    return int(min_p), min_d, int(max_p), max_d, avg, len(points)


def _price_n_days_ago(
    daily: list[tuple[date, int]],
    *,
    reference: date,
    days: int,
) -> int | None:
    if not daily or days < 0:
        return None
    target = reference - timedelta(days=days)
    best: tuple[date, int] | None = None
    for d, p in daily:
        if d > target:
            break
        best = (d, p)
    if best is None:
        return None

    if best[0] > target:
        return None
    return best[1]


def _pct_delta(old: int | None, new: int | None) -> float | None:
    if not old or old <= 0 or new is None:
        return None


    old_f = float(old)
    new_f = float(new)
    return round((new_f - old_f) / old_f * 100.0, 1)


def compute_product_price_stats(
    product: Product,
    *,
    current_price: int | None,
    now: datetime | None = None,
) -> PriceStats:
    now = now or timezone.now()
    today = timezone.localtime(now).date()

    history = list(
        PriceHistory.objects
        .filter(product=product)
        .only('price', 'timestamp')
        .order_by('timestamp')
    )
    daily = _daily_min_series(history)

    if not daily:
        return PriceStats(
            current=current_price,
            min_price=None, min_date=None,
            max_price=None, max_date=None,
            avg_30d=None,
            min_price_7d=None, min_date_7d=None,
            max_price_7d=None, max_date_7d=None,
            avg_7d=None, points_7d=0,
            min_price_30d=None, min_date_30d=None,
            max_price_30d=None, max_date_30d=None,
            points_30d=0,
            delta_7d_pct=None, delta_30d_pct=None,
            is_min_30d=False, is_min_all_time=False,
            drop_alert=False, drop_alert_pct=None,
            history_points=0,
        )

    min_day, min_price = min(daily, key=lambda x: x[1])
    max_day, max_price = max(daily, key=lambda x: x[1])

    # Окна 7д / 30д — те же агрегаты, что и «за всё время», просто на срезе
    (
        min_7d, min_d_7d, max_7d, max_d_7d, avg_7d, pts_7d,
    ) = _window_aggregates(daily, end=today, days=SHORT_WINDOW_DAYS)
    (
        min_30d_w, min_d_30d, max_30d, max_d_30d, avg_30d, pts_30d,
    ) = _window_aggregates(daily, end=today, days=AVG_WINDOW_DAYS)

    price_7d_ago = _price_n_days_ago(daily, reference=today, days=7)
    price_30d_ago = _price_n_days_ago(daily, reference=today, days=30)
    delta_7d = _pct_delta(price_7d_ago, current_price)
    delta_30d = _pct_delta(price_30d_ago, current_price)


    window_start = today - timedelta(days=AVG_WINDOW_DAYS - 1)
    min_30d = min(
        (p for d, p in daily if d >= window_start),
        default=None,
    )
    is_min_30d = bool(
        current_price is not None
        and min_30d is not None
        and current_price <= min_30d
    )
    is_min_all_time = bool(
        current_price is not None
        and current_price <= min_price
    )


    drop_alert = False
    drop_alert_pct: float | None = None
    last_7_points = [p for d, p in daily if today - timedelta(days=6) <= d <= today]
    if (
        current_price is not None
        and len(last_7_points) >= 3
    ):
        avg_7 = sum(last_7_points) / len(last_7_points)
        if avg_7 > 0:
            drop = (avg_7 - current_price) / avg_7
            if drop >= PRICE_DROP_THRESHOLD:
                drop_alert = True
                drop_alert_pct = round(drop * 100.0, 1)

    return PriceStats(
        current=current_price,
        min_price=int(min_price),
        min_date=min_day,
        max_price=int(max_price),
        max_date=max_day,
        avg_30d=avg_30d,
        min_price_7d=min_7d,
        min_date_7d=min_d_7d,
        max_price_7d=max_7d,
        max_date_7d=max_d_7d,
        avg_7d=avg_7d,
        points_7d=pts_7d,
        min_price_30d=min_30d_w,
        min_date_30d=min_d_30d,
        max_price_30d=max_30d,
        max_date_30d=max_d_30d,
        points_30d=pts_30d,
        delta_7d_pct=delta_7d,
        delta_30d_pct=delta_30d,
        is_min_30d=is_min_30d,
        is_min_all_time=is_min_all_time,
        drop_alert=drop_alert,
        drop_alert_pct=drop_alert_pct,
        history_points=len(daily),
    )
