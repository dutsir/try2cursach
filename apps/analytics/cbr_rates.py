"""Получение курсов валют от ЦБ РФ (официальный XML API).

Не требует внешних библиотек — использует requests + xml.etree.
API: https://www.cbr.ru/scripts/XML_daily.asp?date_req=DD/MM/YYYY
"""
from __future__ import annotations

import datetime as _dt
import logging
import xml.etree.ElementTree as ET
from decimal import Decimal

import requests

from .models import CurrencyRate

logger = logging.getLogger(__name__)

CBR_URL = 'https://www.cbr.ru/scripts/XML_daily.asp'

CURRENCY_CHARCODE_MAP = {
    'USD': 'USD',
    'EUR': 'EUR',
    'CNY': 'CNY',
}


def fetch_cbr_rates(date: _dt.date | None = None) -> dict[str, Decimal]:
    """Возвращает {code: rate_to_rub} для поддерживаемых валют."""
    target = date or _dt.date.today()
    params = {'date_req': target.strftime('%d/%m/%Y')}
    resp = requests.get(CBR_URL, params=params, timeout=15)
    resp.raise_for_status()
    resp.encoding = 'windows-1251'

    root = ET.fromstring(resp.text)
    result: dict[str, Decimal] = {}

    for valute in root.findall('Valute'):
        char_code = (valute.findtext('CharCode') or '').strip()
        if char_code not in CURRENCY_CHARCODE_MAP:
            continue
        nominal = int(valute.findtext('Nominal') or '1')
        value_str = (valute.findtext('Value') or '0').replace(',', '.')
        rate = Decimal(value_str) / nominal
        result[char_code] = rate

    return result


def save_rates_for_date(date: _dt.date | None = None) -> int:
    """Загружает курсы ЦБ за дату и сохраняет в БД. Возвращает число новых записей."""
    target = date or _dt.date.today()
    rates = fetch_cbr_rates(target)
    created = 0
    for code, rate in rates.items():
        _, is_new = CurrencyRate.objects.update_or_create(
            currency_code=code,
            date=target,
            defaults={'rate': rate},
        )
        if is_new:
            created += 1
    logger.info('ЦБ РФ %s: сохранено %d курсов (%s)', target, len(rates), ', '.join(rates))
    return created


def backfill_rates(days: int = 90) -> int:
    """Загружает курсы за последние N дней (для инициализации)."""
    total = 0
    today = _dt.date.today()
    for i in range(days):
        d = today - _dt.timedelta(days=i)
        try:
            total += save_rates_for_date(d)
        except Exception:
            logger.warning('Не удалось загрузить курс за %s', d, exc_info=True)
    return total
