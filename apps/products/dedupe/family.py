"""Утилиты двухуровневой дедупликации: ProductFamily ⇄ Product (variant).

Что считается «семьёй»: набор товаров, отличающихся только по варьируемым
характеристикам категории. Для SSD это значит, что Samsung 980 PRO 250GB,
500GB и 1TB — три варианта одной семьи. Для процессора Intel i5-13400F
вариантов нет — семья = один Product.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .constants import VARIANT_SPEC_KEYS_BY_CATEGORY, get_variant_keys


def split_specs(
    specs: dict[str, Any] | None,
    category_slug: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Разбивает specs на (common, variant) согласно правилам категории.

    common — то, что одинаково у всех вариантов семьи (cpu_family, screen_in
    для видеокарт и т. п.). variant — то, чем отличаются варианты внутри семьи
    (storage_gb для SSD, ram_gb для модулей памяти и т. п.).
    """
    src = dict(specs or {})
    variant_keys = get_variant_keys(category_slug)
    common: dict[str, Any] = {}
    variant: dict[str, Any] = {}
    for key, value in src.items():
        if value is None or value == '':
            continue
        if key in variant_keys:
            variant[key] = value
        else:
            common[key] = value
    return common, variant


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def compute_family_key(
    *,
    brand: str,
    model_code: str,
    generation: str = '',
    year: int | None = None,
    common_specs: dict[str, Any] | None = None,
) -> str:
    """sha1 от канонической строки семьи. Не зависит от порядка ключей specs."""
    parts: list[str] = [
        (brand or '').strip().lower(),
        (model_code or '').strip().lower(),
        (generation or '').strip().lower(),
        str(year) if year else '',
        _stable_json(common_specs or {}),
    ]
    payload = '|'.join(parts)
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()


def compute_variant_key(variant_specs: dict[str, Any] | None) -> str:
    """sha1 от variant_specs. Пустые variant → стабильный хэш пустого dict."""
    return hashlib.sha1(_stable_json(variant_specs or {}).encode('utf-8')).hexdigest()


# Токены ёмкостей/объёмов, которые нужно выкинуть из названия товара,
# чтобы получить «семейное» имя для embedding'а. Примеры что чистим:
#   "Samsung 980 PRO 1TB"          → "Samsung 980 PRO"
#   "Kingston Fury Beast 32GB"     → "Kingston Fury Beast"
#   "Kingston Fury Beast 2x16ГБ"   → "Kingston Fury Beast"
#   "Crucial P3 500 ГБ"            → "Crucial P3"
_CAPACITY_RE = re.compile(
    r'\b(?:\d+\s*[xх*]\s*)?\d+(?:[.,]\d+)?\s*(?:TB|ТБ|GB|ГБ|MB|МБ)\b',
    flags=re.IGNORECASE,
)
_WS_RE = re.compile(r'\s+')


def derive_family_name(product_name: str, variant_specs: dict[str, Any] | None = None) -> str:
    """Возвращает «семейное» имя без токенов ёмкостей/объёмов.

    Используется для расчёта embedding'а на уровне семьи (чтобы похожие SSD
    с разной ёмкостью получали близкие векторы, а не разъезжались по ёмкости
    в эмбеддинг-пространстве).

    Аргумент variant_specs пока не используется в логике — оставлен для
    будущего расширения (если понадобится выкидывать токены по реальным
    значениям variant_specs, а не общим регуляркам).
    """
    del variant_specs  # зарезервировано
    if not product_name:
        return ''
    cleaned = _CAPACITY_RE.sub(' ', product_name)
    cleaned = _WS_RE.sub(' ', cleaned).strip()
    return cleaned


# Чистка для SSD: токены, которые встречаются у большинства SSD-карточек и
# не несут идентификации модели. Убираем их, чтобы остался только "бренд + серия".
_SSD_BRACKET_RE = re.compile(r'\[[^\]]*\]')
_SSD_DIM_RE = re.compile(r'\b\d+(?:[.,]\d+)?\s*[″"]?\b(?=\s+(?:SATA|SAS|NVMe|M\.2|PCI[-\s]?E))', re.IGNORECASE)
_SSD_SIZE_FACTOR_RE = re.compile(r'\b(?:M\.2|U\.2|U\.3)\s*\d{4}\b', re.IGNORECASE)
_SSD_NOISE_RE = re.compile(
    r'\b(?:'
    r'накопитель|накопителя|внутренний|внешний|твердотельный'
    r'|жесткий\s+диск|жёсткий\s+диск|диск|серверный'
    r'|SSD|HDD|SATA|SAS|NVMe|PCI[-\s]?E|M\.2|U\.2|U\.3|USB[-\s]?C|USB'
    r'|2\.5["″]|3\.5["″]'
    r'|для\s+(?:ноутбука|пк|сервера)'
    r')\b',
    re.IGNORECASE,
)
# Минимальная длина «MPN-подобного» токена для выкидывания. Реальные серии
# моделей короче 8: P3, MX500, SN570, KC3000, 980 PRO, ESD260C, SXS1000.
# MPN-артикулы обычно длиннее: MZ-V8P1T0BW, WDS500G3B0C, CT1000P3SSD8.
_MPN_TOKEN_MIN_LEN = 8


def _is_mpn_like(token: str) -> bool:
    if len(token) < _MPN_TOKEN_MIN_LEN:
        return False
    has_letter = any(ch.isalpha() for ch in token)
    has_digit = any(ch.isdigit() for ch in token)
    return has_letter and has_digit


def extract_ssd_model_code(name: str, brand: str = '', mpn: str = '') -> str:
    """Возвращает «бренд + серия» для SSD (без ёмкости и без MPN).

    Примеры:
        '2048 ГБ 2.5" SATA накопитель KingSpec P3-2TB [...]'
            → 'kingspec p3'
        '1024 ГБ SSD Samsung 980 PRO MZ-V8P1T0BW'
            → 'samsung 980 pro'   (MPN-токен выкинут как длинный альфа+цифровой)

    Пустая строка означает «не получилось» — вызывающий код должен трактовать
    такой Product как одиночный (family = собственная по product.id).
    """
    del mpn  # пока не используется — серия извлекается из name
    if not name:
        return ''
    s = _SSD_BRACKET_RE.sub(' ', name)
    s = _CAPACITY_RE.sub(' ', s)
    s = _SSD_SIZE_FACTOR_RE.sub(' ', s)
    s = _SSD_DIM_RE.sub(' ', s)
    s = _SSD_NOISE_RE.sub(' ', s)
    tokens: list[str] = []
    for raw in s.split():
        tok = raw.strip(' -_,.')
        if not tok:
            continue
        if _is_mpn_like(tok):
            continue
        tokens.append(tok)
    cleaned = ' '.join(tokens).lower()
    if brand and brand.lower() not in cleaned:
        cleaned = f'{brand.lower()} {cleaned}'.strip()
    if len(cleaned) < 3:
        return ''
    return cleaned


# Категории, использующие extract_ssd_model_code.
_SSD_LIKE_SLUGS: frozenset[str] = frozenset({
    'ssd-nakopiteli',
    'zhestkie-diski-35',
    'servernye-nakopiteli',
    'vneshnie-ssd',
})


# Префиксы / шумовые слова для устройств с конфигурацией внутри названия.
# Используем re.IGNORECASE, поэтому достаточно одного варианта регистра.
_DEVICE_PREFIX_RE = {
    'noutbuki': re.compile(
        r'\b(?:'
        r'ноутбук(?:\s+игровой)?|игровой\s+ноутбук|ультрабук|трансформер'
        r')\b',
        re.IGNORECASE,
    ),
    'sobrannyepk': re.compile(
        r'\b(?:'
        r'мини\s+пк|игровой\s+пк|готовый\s+пк|пк|системный\s+блок|неттоп'
        r')\b',
        re.IGNORECASE,
    ),
    'monobloki': re.compile(r'\bмоноблок\b', re.IGNORECASE),
    'mikrokompyutery': re.compile(
        r'\b(?:микрокомпьютер|одноплатный\s+компьютер)\b', re.IGNORECASE,
    ),
}


# DDR-тип (DDR3 / DDR3L / DDR4 / DDR5 / LPDDR4/5) — критичная часть семьи RAM.
# Без неё DDR4 3200 и DDR5 5600 одной линейки слились бы в одну семью.
_RAM_DDR_RE = re.compile(r'\b(LPDDR[345][X]?|DDR[345][L]?)\b', re.IGNORECASE)
# Частота памяти (например «3200 МГц», «5600 MHz»).
_RAM_FREQ_RE = re.compile(
    r'\b(\d{4,5})\s*(?:МГц|MHz)\b', re.IGNORECASE,
)
_RAM_PREFIX_RE = re.compile(
    r'\b(?:оперативная\s+память|серверная\s+память|память\s+серверная)\b',
    re.IGNORECASE,
)
# Модули kit (например «8 ГБx1 шт», «16 ГБx2 шт»). Эти токены — variant-инфа.
_RAM_KIT_RE = re.compile(
    r'\b\d+\s*(?:GB|ГБ|MB|МБ)\s*[xх*]\s*\d+\s*шт?\b', re.IGNORECASE,
)


def extract_ram_model_code(name: str, brand: str = '') -> str:
    """Возвращает «бренд + серия + DDR-тип + частота» для модуля RAM.

    Примеры:
        'Оперативная память Kingston FURY Beast Black [KF432C16BB/8WP] 8 ГБ
         [DDR4, 8 ГБx1 шт, 3200 МГц, 16(CL)-18-18]'
            → 'kingston fury beast black ddr4 3200'
        'Оперативная память ADATA XPG Lancer Blade [AX5U6000C3616G-DTLABWH]
         32 ГБ [DDR5, 16 ГБx2 шт, 6000 МГц]'
            → 'adata xpg lancer blade ddr5 6000'

    DDR-тип и частота критичны: без них DDR4 3200 и DDR5 5600 одной линейки
    Kingston FURY Beast сольются в одну семью (что неверно — это разные
    стандарты, не варианты).
    """
    if not name:
        return ''
    # Сначала вытаскиваем DDR-тип и частоту, ДО удаления скобок —
    # они часто лежат именно в `[...]` блоке со спеками.
    ddr_match = _RAM_DDR_RE.search(name)
    freq_match = _RAM_FREQ_RE.search(name)
    ddr = (ddr_match.group(1).lower() if ddr_match else '')
    freq = (freq_match.group(1) if freq_match else '')

    s = _SSD_BRACKET_RE.sub(' ', name)
    s = _RAM_KIT_RE.sub(' ', s)
    s = _CAPACITY_RE.sub(' ', s)
    s = _RAM_PREFIX_RE.sub(' ', s)
    tokens: list[str] = []
    for raw in s.split():
        tok = raw.strip(' -_,.')
        if not tok:
            continue
        if _is_mpn_like(tok):
            continue
        tokens.append(tok)
    cleaned = ' '.join(tokens).lower()
    if brand and brand.lower() not in cleaned:
        cleaned = f'{brand.lower()} {cleaned}'.strip()
    # Добавляем DDR-тип и частоту в конец — это часть семейного ключа.
    parts = [cleaned]
    if ddr:
        parts.append(ddr)
    if freq:
        parts.append(freq)
    final = ' '.join(p for p in parts if p).strip()
    if len(final) < 4:
        return ''
    return final


def _is_mpn_like_device(token: str) -> bool:
    """Эвристика «это MPN-артикул?» для laptop/PC.

    Для устройств серии модели чаще начинаются с буквы (X1704VA, B3604CMA,
    PM700SK), а MPN-артикулы — с цифры (90NB13X2-M00ML0, 5301ALXN). Так что:
      - >= 5 символов;
      - содержит и буквы, и цифры;
      - НАЧИНАЕТСЯ с цифры (иначе считаем серией, оставляем).
    """
    if len(token) < 5:
        return False
    if not token[0].isdigit():
        return False
    has_letter = any(ch.isalpha() for ch in token)
    has_digit = any(ch.isdigit() for ch in token)
    return has_letter and has_digit


def extract_device_model_code(
    name: str,
    brand: str = '',
    *,
    prefix_re: re.Pattern[str],
) -> str:
    """Универсальный экстрактор «бренд + линейка модели» для устройств
    с конфигурацией внутри названия (ноутбуки, готовые ПК).

    Стратегия:
      1) убираем `[...]` блоки;
      2) обрезаем всё после первой запятой (там вся конфигурация);
      3) выкидываем шумовые префиксы (Ноутбук / ПК / Мини ПК / ...);
      4) каждый токен разрезаем по первому дефису (X1704VA-AU982 → X1704VA);
      5) выкидываем «MPN-like» головы токенов (начинаются с цифры);
      6) что осталось — бренд + линейка.

    Возвращает '', если префикс категории (Ноутбук/ПК/...) отсутствует
    в исходном имени — такие карточки в этой категории = мусор / битые
    данные, не пытаемся вытаскивать модель.
    """
    if not name:
        return ''
    if not prefix_re.search(name):
        return ''
    s = _SSD_BRACKET_RE.sub(' ', name)
    if ',' in s:
        s = s.split(',', 1)[0]
    s = prefix_re.sub(' ', s)
    s = _CAPACITY_RE.sub(' ', s)
    tokens: list[str] = []
    for raw in s.split():
        tok = raw.strip(' -_,.')
        if not tok:
            continue
        # Откусываем суффикс после первого дефиса — конфигурационный код.
        head = tok.split('-', 1)[0].strip(' _,.')
        if not head:
            continue
        if _is_mpn_like_device(head):
            continue
        tokens.append(head)
    cleaned = ' '.join(tokens).lower()
    if brand and brand.lower() not in cleaned:
        cleaned = f'{brand.lower()} {cleaned}'.strip()
    if len(cleaned) < 3:
        return ''
    return cleaned


_RAM_SLUGS: frozenset[str] = frozenset({'operativnaya-pamyat', 'servernaya-pamyat'})


def _model_code_for_category(
    name: str, brand: str, vendor_code: str, slug: str,
) -> str:
    if slug in _SSD_LIKE_SLUGS:
        return extract_ssd_model_code(name, brand=brand, mpn=vendor_code)
    prefix_re = _DEVICE_PREFIX_RE.get(slug)
    if prefix_re is not None:
        # Для ноутбуков/ПК/моноблоков brand в БД часто неверный (бренд CPU/GPU),
        # поэтому НЕ префиксим — реальный бренд устройства уже есть в имени.
        return extract_device_model_code(name, brand='', prefix_re=prefix_re)
    if slug in _RAM_SLUGS:
        return extract_ram_model_code(name, brand=brand)
    return ''


def make_family_signature(
    *,
    name: str,
    brand: str,
    vendor_code: str,
    specs: dict[str, Any] | None,
    category_slug: str,
) -> dict[str, Any] | None:
    """Готовит family-сигнатуру для одного товара.

    Возвращает None, если категория не поддерживает варианты или модель
    не удалось извлечь — такой Product останется без family (family=None).

    Иначе возвращает dict с:
        model_code     — нормализованная строка «бренд + серия»
        family_name    — то же что и для embedding (derive_family_name)
        common_specs   — specs, общие для семьи
        variant_specs  — specs, отличающие конкретный вариант
        family_key     — sha1 для поиска / создания ProductFamily
        variant_key    — sha1 для поиска / создания варианта внутри семьи
    """
    slug = (category_slug or '').strip().lower()
    if slug not in VARIANT_SPEC_KEYS_BY_CATEGORY and slug not in _SSD_LIKE_SLUGS:
        return None
    model_code = _model_code_for_category(name, brand, vendor_code, slug)
    if not model_code:
        return None
    common, variant = split_specs(specs, slug)
    # Для laptop/PC/моноблоков brand в БД часто мусорный (intel/nvidia/amd —
    # от процессора/GPU). model_code уже содержит реальный бренд устройства,
    # поэтому в family_key brand не нужен.
    family_brand = '' if slug in _DEVICE_PREFIX_RE else brand
    family_key = compute_family_key(
        brand=family_brand, model_code=model_code, common_specs=common,
    )
    variant_key = compute_variant_key(variant)
    return {
        'model_code': model_code,
        'family_name': derive_family_name(name),
        'common_specs': common,
        'variant_specs': variant,
        'family_key': family_key,
        'variant_key': variant_key,
    }


__all__ = (
    'split_specs',
    'compute_family_key',
    'compute_variant_key',
    'derive_family_name',
    'extract_ssd_model_code',
    'extract_device_model_code',
    'extract_ram_model_code',
    'make_family_signature',
)
