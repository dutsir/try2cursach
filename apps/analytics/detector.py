from __future__ import annotations

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
class AnomalyResult:
    anomaly_type: str
    severity: str
    description: str


def _get_recent_prices(product: Product, limit: int = 14) -> list[Decimal]:
    records = (
        PriceHistory.objects
        .filter(product=product)
        .order_by('-timestamp')[:limit]
    )
    return [r.price for r in reversed(records)]


def detect_spike(prices: list[Decimal]) -> AnomalyResult | None:
    if len(prices) < 2:
        return None

    prev, curr = float(prices[-2]), float(prices[-1])
    if prev == 0:
        return None

    change = abs(curr - prev) / prev

    if change > SPIKE_THRESHOLD:
        direction = 'рост' if curr > prev else 'падение'
        severity = 'high' if change > 0.30 else 'medium'
        return AnomalyResult(
            anomaly_type=Anomaly.AnomalyType.SPIKE,
            severity=severity,
            description=(
                f'Резкий {direction} цены которые могут: {prev:.0f}₽ → {curr:.0f}₽ '
                f'({change:.1%})'
            ),
        )
    return None


def detect_manipulation(prices: list[Decimal]) -> AnomalyResult | None:
    if len(prices) < 4:
        return None

    fp = [float(p) for p in prices]

    for i in range(len(fp) - 3):
        base = fp[i]
        if base == 0:
            continue
        peak = max(fp[i + 1], fp[i + 2])
        rise = (peak - base) / base

        if rise >= MANIPULATION_RISE_THRESHOLD:
            after = fp[i + 3] if i + 3 < len(fp) else fp[-1]
            if after < base:
                return AnomalyResult(
                    anomaly_type=Anomaly.AnomalyType.MANIPULATION,
                    severity='high',
                    description=(
                        f'Подозрение на манипуляцию: цена поднялась с {base:.0f}₽ '
                        f'до {peak:.0f}₽ (+{rise:.1%}), затем упала до {after:.0f}₽ '
                        f'(ниже исходной).'
                    ),
                )
    return None


def detect_cyclic(prices: list[Decimal]) -> AnomalyResult | None:
    if len(prices) < MIN_PRICES_FOR_FFT:
        return None

    signal = np.array([float(p) for p in prices], dtype=np.float64)

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
        return AnomalyResult(
            anomaly_type=Anomaly.AnomalyType.CYCLIC,
            severity='low',
            description=(
                f'Обнаружено циклическое колебание цены с периодом '
                f'~{period:.1f} записей (доминантная гармоника: {dominant_ratio:.1%} мощности). '
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

    prices = _get_recent_prices(product, limit=14)

    if len(prices) < MIN_PRICES_FOR_ANALYSIS:
        logger.debug(
            'Недостаточно данных для анализа товара %s (%d записей)',
            product.name, len(prices),
        )
        return []

    detectors = [detect_spike, detect_manipulation, detect_cyclic]
    created_anomalies: list[Anomaly] = []

    for detector_fn in detectors:
        result = detector_fn(prices)
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
