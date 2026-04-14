from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from scipy.fft import rfft, rfftfreq

from django.utils import timezone

from apps.prices.models import PriceHistory
from apps.products.models import Product
from .models import Anomaly

logger = logging.getLogger(__name__)

SPIKE_THRESHOLD = 0.10
MANIPULATION_RISE_THRESHOLD = 0.10
CYCLIC_POWER_THRESHOLD = 0.3
MIN_PRICES_FOR_ANALYSIS = 3
MIN_PRICES_FOR_FFT = 6


@dataclass
class PricePoint:
    price: Decimal
    timestamp: _dt.datetime


@dataclass
class AnomalyResult:
    anomaly_type: str
    severity: str
    description: str


def _get_recent_records(product: Product, limit: int = 14) -> list[PricePoint]:
    records = (
        PriceHistory.objects
        .filter(product=product)
        .order_by('-timestamp')[:limit]
    )
    return [PricePoint(price=r.price, timestamp=r.timestamp) for r in reversed(records)]


def _get_recent_prices(product: Product, limit: int = 14) -> list[Decimal]:
    return [r.price for r in _get_recent_records(product, limit)]


def _days_between(a: _dt.datetime, b: _dt.datetime) -> float:
    return abs((b - a).total_seconds()) / 86400


def _find_past_similar_spike(product: Product, change_pct: float, current_ts: _dt.datetime) -> str:
    """Check if a similar spike happened in older history (beyond last 14 records)."""
    older = (
        PriceHistory.objects
        .filter(product=product, timestamp__lt=current_ts - _dt.timedelta(days=14))
        .order_by('-timestamp')[:60]
    )
    pts = list(reversed(older))
    for i in range(1, len(pts)):
        prev_p, curr_p = float(pts[i - 1].price), float(pts[i].price)
        if prev_p == 0:
            continue
        old_change = abs(curr_p - prev_p) / prev_p
        if old_change >= change_pct * 0.7:
            ago = _days_between(pts[i].timestamp, current_ts)
            return f' Аналогичный скачок ({old_change:.1%}) наблюдался {ago:.0f} дн. назад ({pts[i].timestamp:%d.%m.%Y}).'
    return ''


def detect_spike(records: list[PricePoint], product: Product | None = None) -> AnomalyResult | None:
    if len(records) < 2:
        return None

    prev_r, curr_r = records[-2], records[-1]
    prev, curr = float(prev_r.price), float(curr_r.price)
    if prev == 0:
        return None

    change = abs(curr - prev) / prev
    if change <= SPIKE_THRESHOLD:
        return None

    direction = 'вырос' if curr > prev else 'упал'
    direction_noun = 'рост' if curr > prev else 'падение'
    severity = 'high' if change > 0.30 else 'medium'
    days = _days_between(prev_r.timestamp, curr_r.timestamp)

    past_hint = ''
    if product is not None:
        past_hint = _find_past_similar_spike(product, change, curr_r.timestamp)

    desc = (
        f'Резкий {direction_noun} цены на {change:.1%} за {days:.1f} дн.: '
        f'{prev:.0f}₽ ({prev_r.timestamp:%d.%m.%Y}) → {curr:.0f}₽ ({curr_r.timestamp:%d.%m.%Y}). '
        f'Цена {direction} на {abs(curr - prev):.0f}₽.'
        f'{past_hint}'
    )
    return AnomalyResult(anomaly_type=Anomaly.AnomalyType.SPIKE, severity=severity, description=desc)


def detect_manipulation(records: list[PricePoint], **_kw) -> AnomalyResult | None:
    if len(records) < 4:
        return None

    for i in range(len(records) - 3):
        base = float(records[i].price)
        if base == 0:
            continue
        peak_val = max(float(records[i + 1].price), float(records[i + 2].price))
        peak_r = records[i + 1] if float(records[i + 1].price) >= float(records[i + 2].price) else records[i + 2]
        rise = (peak_val - base) / base

        if rise >= MANIPULATION_RISE_THRESHOLD:
            after_r = records[i + 3] if i + 3 < len(records) else records[-1]
            after = float(after_r.price)
            if after < base:
                days_up = _days_between(records[i].timestamp, peak_r.timestamp)
                days_down = _days_between(peak_r.timestamp, after_r.timestamp)
                return AnomalyResult(
                    anomaly_type=Anomaly.AnomalyType.MANIPULATION,
                    severity='high',
                    description=(
                        f'Подозрение на манипуляцию: цена поднялась с {base:.0f}₽ '
                        f'({records[i].timestamp:%d.%m}) до {peak_val:.0f}₽ ({peak_r.timestamp:%d.%m}) '
                        f'(+{rise:.1%}, за {days_up:.0f} дн.), '
                        f'затем упала до {after:.0f}₽ ({after_r.timestamp:%d.%m}) '
                        f'за {days_down:.0f} дн. — ниже исходной на {base - after:.0f}₽.'
                    ),
                )
    return None


def detect_cyclic(records: list[PricePoint], **_kw) -> AnomalyResult | None:
    if len(records) < MIN_PRICES_FOR_FFT:
        return None

    signal = np.array([float(r.price) for r in records], dtype=np.float64)
    detrended = signal - np.linspace(signal[0], signal[-1], len(signal))

    if np.std(detrended) < 1.0:
        return None

    spectrum = np.abs(rfft(detrended))
    freqs = rfftfreq(len(detrended))

    if len(spectrum) < 2:
        return None

    spectrum_no_dc = spectrum[1:]
    freqs_no_dc = freqs[1:]
    total_power = np.sum(spectrum_no_dc)

    if total_power < 1e-6:
        return None

    dominant_idx = np.argmax(spectrum_no_dc)
    dominant_power = spectrum_no_dc[dominant_idx]
    dominant_ratio = dominant_power / total_power
    dominant_freq = freqs_no_dc[dominant_idx]

    if dominant_ratio > CYCLIC_POWER_THRESHOLD and dominant_freq > 0:
        period = 1.0 / dominant_freq
        span = _days_between(records[0].timestamp, records[-1].timestamp)
        approx_days = (span / len(records)) * period if len(records) > 1 else period
        return AnomalyResult(
            anomaly_type=Anomaly.AnomalyType.CYCLIC,
            severity='low',
            description=(
                f'Обнаружено циклическое колебание цены с периодом ~{approx_days:.0f} дн. '
                f'({period:.1f} записей, доминантная гармоника: {dominant_ratio:.1%} мощности) '
                f'за период {records[0].timestamp:%d.%m.%Y}–{records[-1].timestamp:%d.%m.%Y}. '
                f'Это может указывать на автоматическое ценообразование.'
            ),
        )
    return None


def run_full_detection(product_id: int) -> list[Anomaly]:
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        logger.warning('Товар id=%d не найден для анализа аномалий', product_id)
        return []

    records = _get_recent_records(product, limit=14)

    if len(records) < MIN_PRICES_FOR_ANALYSIS:
        logger.debug(
            'Недостаточно данных для анализа товара %s (%d записей)',
            product.name, len(records),
        )
        return []

    detectors = [
        lambda recs: detect_spike(recs, product=product),
        detect_manipulation,
        detect_cyclic,
    ]
    created_anomalies: list[Anomaly] = []

    for detector_fn in detectors:
        result = detector_fn(records)
        if result is None:
            continue

        recent_duplicate = Anomaly.objects.filter(
            product=product,
            anomaly_type=result.anomaly_type,
            resolved=False,
            detected_at__gte=timezone.now() - timezone.timedelta(hours=24),
        ).exists()

        if recent_duplicate:
            logger.debug(
                'Дублирующая аномалия %s для %s — пропуск',
                result.anomaly_type, product.name,
            )
            continue

        anomaly = Anomaly.objects.create(
            product=product,
            anomaly_type=result.anomaly_type,
            severity=result.severity,
            description=result.description,
        )
        created_anomalies.append(anomaly)
        logger.info(
            'Аномалия [%s/%s] для %s: %s',
            result.anomaly_type, result.severity, product.name, result.description,
        )

    return created_anomalies
