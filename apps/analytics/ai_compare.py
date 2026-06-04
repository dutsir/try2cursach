"""AI-сравнение товаров через Google Gemini API.

Генерирует краткий вердикт (3-5 предложений) о наборе товаров с подсветкой
лучшего варианта. Кэширует результат в Redis (ключ зависит от ids и цен,
чтобы при обновлении цены пересчитывался вердикт).
"""
from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_BASE = 'https://generativelanguage.googleapis.com'
GEMINI_URL = '{base}/v1beta/models/{model}:generateContent?key={api_key}'

DEFAULT_MODEL = 'gemini-2.0-flash'
REQUEST_TIMEOUT = 15  # секунд


class AIServiceError(Exception):
    """Ошибка обращения к LLM (нет ключа, timeout, etc.)."""


def _cache_key(items: list[dict]) -> str:
    """Хеш по id + цене каждого товара."""
    parts = []
    for it in sorted(items, key=lambda x: x['id']):
        price = it.get('best_offer', {}).get('price') if it.get('best_offer') else None
        parts.append(f"{it['id']}:{price}")
    raw = '|'.join(parts)
    h = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]
    return f'ai_compare:{h}'


def _build_prompt(items: list[dict]) -> str:
    """Формирует промпт для Gemini.

    Принимает товары из CompareView (id, name, brand, category, best_offer,
    stats, specs).
    """
    category = items[0].get('category', {}).get('name', 'Товары') if items else 'Товары'

    lines = []
    for i, item in enumerate(items, 1):
        name = item.get('name', 'Без названия')
        brand = item.get('brand', '')
        price = '—'
        store = ''
        if item.get('best_offer'):
            price = f"{item['best_offer'].get('price', '—')} ₽"
            store = item['best_offer'].get('source_display', '')

        rating = item.get('stats', {}).get('rating')
        reviews = item.get('stats', {}).get('reviews_count')

        specs = item.get('specs', {}) or {}
        spec_lines = []
        for key in ['ram_gb', 'storage_gb', 'gpu_family', 'cpu_family', 'screen_in', 'color']:
            if key in specs and specs[key]:
                spec_lines.append(f"{key}={specs[key]}")
        nested = specs.get('specs')
        if isinstance(nested, dict):
            for k, v in nested.items():
                spec_lines.append(f"{k}={v}")

        line = f"{i}. {name}"
        if brand:
            line += f" [{brand}]"
        line += f", цена: {price}"
        if store:
            line += f" ({store})"
        if rating:
            line += f", рейтинг: {rating}"
        if reviews:
            line += f", отзывов: {reviews}"
        if spec_lines:
            line += f", характеристики: {', '.join(spec_lines)}"
        lines.append(line)

    products_block = '\n'.join(lines)

    return f"""Ты — эксперт по компьютерной технике и электронике. Проанализируй данные о товарах и дай краткое заключение для покупателя.

КАТЕГОРИЯ: {category}

ТОВАРЫ:
{products_block}

ПРАВИЛА ОТВЕТА:
- Язык: русский
- Объём: 3-5 предложений, без вводных фраз
- Не используй markdown, звёздочки, заголовки — только обычный текст
- Сравни ключевые параметры и цену
- В конце дай чёткую рекомендацию: какой товар лучший выбор и почему
- Если данные слишком похожи или не хватает спеков, скажи это честно
- Не выдумывай характеристики которых нет в данных

Твой вердикт:"""


def _call_gemini(prompt: str) -> str:
    """Один HTTP-запрос к Gemini. Возвращает text вердикта.

    На 503 (UNAVAILABLE, частая проблема free tier) делает 2 ретрая с backoff.
    """
    import time

    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise AIServiceError('GEMINI_API_KEY не настроен в .env')

    model = getattr(settings, 'GEMINI_MODEL', DEFAULT_MODEL)
    base = getattr(settings, 'GEMINI_BASE_URL', DEFAULT_GEMINI_BASE).rstrip('/')
    url = GEMINI_URL.format(base=base, model=model, api_key=api_key)

    payload = {
        'contents': [{
            'parts': [{'text': prompt}]
        }],
        'generationConfig': {
            'temperature': 0.4,
            'maxOutputTokens': 400,
            'thinkingConfig': {'thinkingBudget': 0},
        },
    }

    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        except requests.Timeout:
            raise AIServiceError('Gemini API не ответил за 15 секунд')
        except requests.RequestException as exc:
            raise AIServiceError(f'Ошибка сети: {exc}')

        if response.status_code == 200:
            try:
                data = response.json()
                text = data['candidates'][0]['content']['parts'][0]['text'].strip()
            except (KeyError, IndexError, ValueError) as exc:
                logger.error('Gemini API bad response: %s', response.text[:500])
                raise AIServiceError(f'Не удалось разобрать ответ модели: {exc}')
            if not text:
                raise AIServiceError('Модель вернула пустой ответ')
            return text

        # 503 = временный overload, повторяем; другие ошибки сразу пробрасываем
        if response.status_code == 503 and attempt < 2:
            logger.warning('Gemini 503 (попытка %d), ретрай через %d сек', attempt + 1, attempt + 1)
            time.sleep(attempt + 1)
            last_error = '503'
            continue

        logger.error('Gemini API error %s: %s', response.status_code, response.text[:500])
        raise AIServiceError(f'Gemini API вернул {response.status_code}')

    raise AIServiceError(f'Gemini API перегружен ({last_error}), попробуй позже')


def generate_compare_summary(items: list[dict]) -> dict[str, Any]:
    """Главная функция: генерит AI-вердикт по списку товаров.

    Args:
        items: список dict-ов в формате CompareView (id, name, best_offer, stats, specs)

    Returns:
        {'verdict': str, 'cached': bool}
    """
    if not items or len(items) < 2:
        raise AIServiceError('Нужно минимум 2 товара для сравнения')

    cache_key = _cache_key(items)
    cached = cache.get(cache_key)
    if cached:
        logger.info('AI compare: cache hit for %s', cache_key)
        return {'verdict': cached, 'cached': True}

    prompt = _build_prompt(items)
    logger.info('AI compare: cache miss, calling Gemini (prompt %d chars)', len(prompt))
    verdict = _call_gemini(prompt)

    ttl = getattr(settings, 'AI_COMPARE_CACHE_TTL', 86400)
    cache.set(cache_key, verdict, timeout=ttl)

    return {'verdict': verdict, 'cached': False}
