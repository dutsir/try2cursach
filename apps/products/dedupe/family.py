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


# ═══════════════════════════════════════════════════════════════════════════
# CPU экстрактор (processory, servernye-processory)
# ═══════════════════════════════════════════════════════════════════════════

# Префикс категории
_CPU_PREFIX_RE = re.compile(r'\bпроцессор\b', re.IGNORECASE)

# Семейства CPU AMD: Ryzen / Threadripper / EPYC / FX / Athlon
# Пример: "AMD Ryzen 5 5600XT" → "amd ryzen 5 5600xt"
# Пример: "AMD Ryzen Threadripper 1900X" → "amd ryzen threadripper 1900x"
# Пример: "AMD Ryzen 5 PRO 5350G" → "amd ryzen 5 pro 5350g"
_CPU_AMD_RE = re.compile(
    r'\bAMD\s+'
    r'(?P<family>Ryzen|Threadripper|EPYC|FX|Athlon|Phenom)\s*'
    r'(?P<series>(?:Threadripper\s+)?(?:PRO\s+)?\d?\s*\d*\s*[\w\d]+'
    r'(?:[-\s]\d+(?:XT|X3D|X|F|G|GE|H|HS|HX|U)?)?)',
    re.IGNORECASE,
)

# Семейства CPU Intel: Core / Pentium / Celeron / Xeon
# Пример: "Intel Core i7-13700K" → "intel core i7-13700k"
# Пример: "Intel Core Ultra 5 235" → "intel core ultra 5 235"
# Пример: "Intel Xeon Gold 6248" → "intel xeon gold 6248"
#
# Для Core Ultra: серия — это число (5/7/9) + пробел + номер модели (235/255H)
# Для обычного Core: серия — это i3/i5/i7/i9 + дефис + номер (13700K)
_CPU_INTEL_RE = re.compile(
    r'\bIntel\s+'
    r'(?P<family>Core\s+Ultra|Core|Pentium|Celeron|Xeon|Atom)\s+'
    r'(?P<series>'
    r'(?:Gold|Silver|Bronze|Platinum|Diamond)?\s*'
    r'(?:i[3579][-\s]?[\w\d]+(?:[A-Z]+)?'  # i7-13700K
    r'|\d+\s+\d+[A-Z]*'  # Ultra: 5 235
    r'|[\w\d-]+'  # generic fallback
    r')'
    r')',
    re.IGNORECASE,
)


def extract_cpu_model_code(name: str, brand: str = '') -> str:
    """Извлекает model_code для CPU.

    Примеры:
        'Процессор AMD Ryzen 5 5600XT, AM4, OEM [100-000001585]'
            → 'amd ryzen 5 5600xt'
        'Процессор Intel Core i7-13700K BOX [LGA 1700, ...]'
            → 'intel core i7-13700k'
        'Процессор Intel Core Ultra 5 235, LGA 1851, OEM'
            → 'intel core ultra 5 235'
    """
    if not name or not _CPU_PREFIX_RE.search(name):
        return ''
    # Обрезаем после первой запятой (там сокет, BOX/OEM, тех. характеристики)
    s = name.split(',', 1)[0]
    s = _SSD_BRACKET_RE.sub(' ', s)

    # AMD
    m = _CPU_AMD_RE.search(s)
    if m:
        family = m.group('family').lower().strip()
        series = m.group('series').lower().strip()
        # Убираем повторы и нормализуем пробелы
        series = _WS_RE.sub(' ', series).strip()
        return f'amd {family} {series}'.strip()

    # Intel
    m = _CPU_INTEL_RE.search(s)
    if m:
        family = m.group('family').lower().strip()
        series = m.group('series').lower().strip()
        series = _WS_RE.sub(' ', series).strip()
        return f'intel {family} {series}'.strip()

    return ''


# ═══════════════════════════════════════════════════════════════════════════
# GPU экстрактор (videokarty)
# ═══════════════════════════════════════════════════════════════════════════

_GPU_PREFIX_RE = re.compile(r'\bвидеокарта\b', re.IGNORECASE)

# Чип NVIDIA: RTX 5060 Ti / GTX 1650 / RTX 4060 / GTX 1660 SUPER
# Захватываем: семейство + число + (Ti|SUPER) опц.
_GPU_NVIDIA_CHIP_RE = re.compile(
    r'\b(?:GeForce\s+)?(?P<series>RTX|GTX|GT)\s*'
    r'(?P<number>\d{3,4})\s*'
    r'(?P<suffix>Ti|TI|SUPER|S|XT)?'
    r'(?:\s*(?:Ti|TI|SUPER|S|XT))?',
    re.IGNORECASE,
)

# Чип AMD: RX 9070XT / RX 7900 XTX / Radeon RX 6600
_GPU_AMD_CHIP_RE = re.compile(
    r'\b(?:Radeon\s+)?RX\s*'
    r'(?P<number>\d{3,4})\s*'
    r'(?P<suffix>XT|X|XTX|XL|XE)?',
    re.IGNORECASE,
)

# Бренды производителей видеокарт (отличаются от чипа: MSI/ASUS/Gigabyte vs NVIDIA/AMD)
_GPU_VENDOR_BRANDS = frozenset({
    'asus', 'msi', 'gigabyte', 'palit', 'inno3d', 'kfa2', 'pny',
    'evga', 'zotac', 'sapphire', 'powercolor', 'xfx', 'asrock',
    'biostar', 'afox', 'colorful', 'gainward', 'manli',
})


def extract_gpu_model_code(name: str, brand: str = '') -> str:
    """Извлекает model_code для GPU = "vendor + chip" (без объёма памяти).

    Объём памяти (8GB, 12GB) — это variant внутри семьи.

    Примеры:
        'Видеокарта MSI GeForce RTX 4060 GAMING X 8GB' → 'msi rtx 4060'
        'Видеокарта Gigabyte RTX 5060TI GV-N506TGAMING-8GD' → 'gigabyte rtx 5060ti'
        'Видеокарта PowerColor AMD Radeon RX 7900 XT 20GB' → 'powercolor rx 7900 xt'
    """
    if not name or not _GPU_PREFIX_RE.search(name):
        return ''
    s = _GPU_PREFIX_RE.sub(' ', name)
    s = _SSD_BRACKET_RE.sub(' ', s)

    # Находим vendor (производитель карты, не чип)
    vendor = ''
    for token in s.lower().split():
        clean = token.strip('.,/[]()')
        if clean in _GPU_VENDOR_BRANDS:
            vendor = clean
            break

    # Находим чип
    chip = ''
    # Сначала AMD (т.к. RX явный)
    m = _GPU_AMD_CHIP_RE.search(s)
    if m:
        number = m.group('number')
        suffix = (m.group('suffix') or '').lower()
        chip = f'rx {number}{suffix}'.strip()
    else:
        # NVIDIA
        m = _GPU_NVIDIA_CHIP_RE.search(s)
        if m:
            series = m.group('series').lower()
            number = m.group('number')
            suffix = (m.group('suffix') or '').lower()
            chip = f'{series} {number}{suffix}'.strip()

    if not chip:
        return ''

    # Если vendor не нашёлся — используем brand из БД (для AFOX, Biostar)
    if not vendor:
        vendor = (brand or '').lower().strip()
        # nvidia/amd — это чип, не vendor (отбрасываем)
        if vendor in ('nvidia', 'amd'):
            vendor = ''

    if vendor:
        return f'{vendor} {chip}'.strip()
    return chip


# ═══════════════════════════════════════════════════════════════════════════
# Motherboard экстрактор (materinskie-platy, servernye-materinskie-platy)
# ═══════════════════════════════════════════════════════════════════════════

_MB_PREFIX_RE = re.compile(r'\bматеринская\s+плата\b', re.IGNORECASE)
# Шумовые токены MB — не часть модели
_MB_NOISE_RE = re.compile(
    r'\b(?:Socket|LGA|AM[345]|TR4|sTRX4|sWRX8|FCBGA|ATX|mATX|micro-?ATX|'
    r'mini-?ITX|E-?ATX|XL-?ATX|EATX|DDR[3-5]|PCIe?|Ret|OEM|BOX|'
    r'AMD|Intel)\b',
    re.IGNORECASE,
)


def extract_mb_model_code(name: str, brand: str = '') -> str:
    """Извлекает model_code для материнской платы.

    Стратегия: бренд + серия + модель (например "asus rog strix x870-i gaming wifi").

    Примеры:
        'Материнская плата ASUS ROG STRIX X870-I GAMING WIFI [AM5, ...]'
            → 'asus rog strix x870-i gaming wifi'
        'Материнская плата Gigabyte B760M GAMING X WIFI6E GEN5, Socket LGA 1700, ...'
            → 'gigabyte b760m gaming x wifi6e gen5'
    """
    if not name or not _MB_PREFIX_RE.search(name):
        return ''
    s = _MB_PREFIX_RE.sub(' ', name)
    s = _SSD_BRACKET_RE.sub(' ', s)
    # Обрезаем всё после первой запятой (там Socket, формфактор)
    if ',' in s:
        s = s.split(',', 1)[0]
    s = _MB_NOISE_RE.sub(' ', s)
    s = _WS_RE.sub(' ', s).strip()
    cleaned = s.lower().strip()
    if not cleaned:
        return ''
    if brand and brand.lower() not in cleaned:
        cleaned = f'{brand.lower()} {cleaned}'
    if len(cleaned) < 3:
        return ''
    return cleaned


# ═══════════════════════════════════════════════════════════════════════════
# Monitor экстрактор (monitory)
# ═══════════════════════════════════════════════════════════════════════════

_MONITOR_PREFIX_RE = re.compile(
    r'(?:^|\s)(?:\d+(?:\.\d+)?\s*["″]?\s*)?монитор\b', re.IGNORECASE,
)
_MONITOR_SIZE_RE = re.compile(r'\b\d{2}(?:\.\d+)?["″]?(?=\s+монитор)', re.IGNORECASE)


def extract_monitor_model_code(name: str, brand: str = '') -> str:
    """Извлекает model_code для монитора.

    Примеры:
        '27" Монитор Acer Vero B277KLBbmiiprzx, 3840x2160, IPS, ...'
            → 'acer vero b277klbbmiiprzx'
        '27" Монитор Gigabyte GS27FA, 1920x1080, ...'
            → 'gigabyte gs27fa'
    """
    if not name:
        return ''
    if not _MONITOR_PREFIX_RE.search(name):
        return ''
    s = _MONITOR_PREFIX_RE.sub(' ', name)
    s = _SSD_BRACKET_RE.sub(' ', s)
    s = _MONITOR_SIZE_RE.sub(' ', s)
    if ',' in s:
        s = s.split(',', 1)[0]
    s = _WS_RE.sub(' ', s).strip()
    cleaned = s.lower().strip()
    if not cleaned:
        return ''
    if brand and brand.lower() not in cleaned:
        cleaned = f'{brand.lower()} {cleaned}'
    if len(cleaned) < 3:
        return ''
    return cleaned


# ═══════════════════════════════════════════════════════════════════════════
# PSU экстрактор (bloki-pitaniya, servernye-bloki-pitaniya)
# ═══════════════════════════════════════════════════════════════════════════

_PSU_PREFIX_RE = re.compile(r'\bблок\s+питания\b', re.IGNORECASE)


def extract_psu_model_code(name: str, brand: str = '') -> str:
    """Извлекает model_code для БП.

    Примеры:
        'Блок питания Gigabyte GP-P650G, 650Вт, 80 PLUS GOLD, ...'
            → 'gigabyte gp-p650g'
        'Блок питания CHIEFTEC Vita SM3 BPX-650-C, 650Вт, ...'
            → 'chieftec vita sm3 bpx-650-c'
    """
    if not name or not _PSU_PREFIX_RE.search(name):
        return ''
    s = _PSU_PREFIX_RE.sub(' ', name)
    s = _SSD_BRACKET_RE.sub(' ', s)
    if ',' in s:
        s = s.split(',', 1)[0]
    s = _WS_RE.sub(' ', s).strip()
    cleaned = s.lower().strip()
    if not cleaned:
        return ''
    if brand and brand.lower() not in cleaned:
        cleaned = f'{brand.lower()} {cleaned}'
    if len(cleaned) < 3:
        return ''
    return cleaned


# ═══════════════════════════════════════════════════════════════════════════
# УНИВЕРСАЛЬНЫЙ ЭКСТРАКТОР для категорий "Префикс + Brand + Model"
# ═══════════════════════════════════════════════════════════════════════════

# Шумовые слова для всех категорий (цвета, упаковка, типы)
_GENERIC_NOISE_RE = re.compile(
    r'\b(?:'
    r'черный|белый|серый|серебристый|красный|синий|зелёный|зеленый|'
    r'желтый|золотистый|розовый|фиолетовый|оранжевый|коричневый|'
    r'бежевый|бирюзовый|графитовый|темно[-\s]?серый|тёмно[-\s]?серый|'
    r'светло[-\s]?серый|black|white|grey|gray|silver|red|blue|green|'
    r'yellow|gold|pink|purple|orange|brown|beige|graphite|'
    r'BOX|OEM|Ret|retail|RGB|ARGB|LED'
    r')\b',
    re.IGNORECASE,
)

# Регекс для очистки пустых скобок и одиночных символов
_EMPTY_BRACKETS_RE = re.compile(r'\(\s*\)|\[\s*\]|\{\s*\}')


def _generic_brand_model_extractor(
    name: str,
    brand: str,
    prefix_re: re.Pattern[str],
    *,
    extra_noise_re: re.Pattern[str] | None = None,
    cut_at_first_comma: bool = True,
) -> str:
    """Универсальный экстрактор: префикс категории + brand + model.

    Стратегия:
      1. Удалить префикс категории
      2. Удалить [...] блоки (там обычно артикулы)
      3. Обрезать всё после первой запятой (там характеристики)
      4. Удалить шумовые токены (цвета, упаковка)
      5. Добавить brand если его нет в результате

    Args:
        name: исходное название
        brand: бренд из БД (опционально, добавляется если не в имени)
        prefix_re: regex префикса категории
        extra_noise_re: дополнительные шумовые слова
        cut_at_first_comma: обрезать после ',' (обычно True)
    """
    if not name or not prefix_re.search(name):
        return ''
    s = prefix_re.sub(' ', name)
    s = _SSD_BRACKET_RE.sub(' ', s)
    if cut_at_first_comma and ',' in s:
        s = s.split(',', 1)[0]
    s = _GENERIC_NOISE_RE.sub(' ', s)
    if extra_noise_re is not None:
        s = extra_noise_re.sub(' ', s)
    s = _EMPTY_BRACKETS_RE.sub(' ', s)
    # Удаляем одиночные скобки/символы оставшиеся после фильтрации
    s = re.sub(r'\s[(){}\[\]]+\s', ' ', s)
    s = _WS_RE.sub(' ', s).strip()
    cleaned = s.lower().strip()
    if not cleaned:
        return ''
    if brand and brand.lower() not in cleaned:
        cleaned = f'{brand.lower()} {cleaned}'
    if len(cleaned) < 3:
        return ''
    return cleaned


# ═══════════════════════════════════════════════════════════════════════════
# Простые экстракторы (через universal)
# ═══════════════════════════════════════════════════════════════════════════

# Карты памяти: "Карта памяти SDXC UHS-I U1 Kingston Canvas Select Plus 512 ГБ..."
_SD_PREFIX_RE = re.compile(
    r'\b(?:карта\s+памяти|microSDXC|SDXC|microSDHC|SDHC|microSD|CompactFlash|CF)\b',
    re.IGNORECASE,
)
_SD_CLASS_RE = re.compile(
    r'\b(?:UHS-[I|II|III]+|U[1-3]|Class\s*\d+|V\d+|A\d+)\b', re.IGNORECASE,
)
_SD_SPEED_RE = re.compile(r'\d+\s*(?:МБ/с|MB/s|Mb/s|МБ\/с)', re.IGNORECASE)


def extract_memory_card_model_code(name: str, brand: str = '') -> str:
    """SD/microSD карты: 'kingston canvas select plus'.

    Capacity (512GB) — variant, скорость и класс — common specs.
    """
    if not name:
        return ''
    s = _SD_CLASS_RE.sub(' ', name)
    s = _SD_SPEED_RE.sub(' ', s)
    s = _CAPACITY_RE.sub(' ', s)
    return _generic_brand_model_extractor(
        s, brand, _SD_PREFIX_RE,
    )


# Микрофоны: "Микрофон Ritmix RWM-101, черный [15115476]"
_MIC_PREFIX_RE = re.compile(r'\bмикрофон\b', re.IGNORECASE)


def extract_microphone_model_code(name: str, brand: str = '') -> str:
    return _generic_brand_model_extractor(name, brand, _MIC_PREFIX_RE)


# Звуковые карты: "Внешняя звуковая карта BEHRINGER U-CONTROL UCA202"
_SOUNDCARD_PREFIX_RE = re.compile(
    r'\b(?:внешняя\s+)?(?:внутренняя\s+)?звуковая\s+карта\b', re.IGNORECASE,
)
_SOUNDCARD_NOISE_RE = re.compile(
    r'\b(?:USB[-\s]?Type[-\s]?[AC]|USB[-\s]?[AC]|USB\s+\d\.\d|'
    r'формат\s+звуковой\s+карты|\d+\.\d+|ASIO|\d+\s*бит|\d+\s*кГц|\d+\s*Гц)\b',
    re.IGNORECASE,
)


def extract_soundcard_model_code(name: str, brand: str = '') -> str:
    return _generic_brand_model_extractor(
        name, brand, _SOUNDCARD_PREFIX_RE,
        extra_noise_re=_SOUNDCARD_NOISE_RE,
    )


# Внешние HDD: "5ТБ Внешний диск HDD WD My Passport WDBPKJ0050BBK-WESN, USB 3.2..."
_EXT_HDD_PREFIX_RE = re.compile(
    r'\b(?:\d+\s*[ТGT]?Б\s+)?'
    r'(?:внешний\s+диск|внешний\s+ssd|внешний\s+hdd|portable\s+ssd)\b'
    r'(?:\s+(?:HDD|SSD))?',
    re.IGNORECASE,
)
_EXT_HDD_NOISE_RE = re.compile(
    r'\b(?:USB[-\s]?Type[-\s]?[AC]|USB\s+\d(?:\.\d)?(?:\s*Gen\s*\d)?)\b',
    re.IGNORECASE,
)


def extract_ext_hdd_model_code(name: str, brand: str = '') -> str:
    """Внешний HDD: 'wd my passport' (без MPN).

    Размер (1TB, 5TB) — variant. Brand часто внутри названия.
    """
    if not name:
        return ''
    s = _CAPACITY_RE.sub(' ', name)
    return _generic_brand_model_extractor(
        s, brand, _EXT_HDD_PREFIX_RE,
        extra_noise_re=_EXT_HDD_NOISE_RE,
    )


# NAS: "Сетевое хранилище (NAS) TerraMaster F4-212"
_NAS_PREFIX_RE = re.compile(
    r'сетевое\s+хранилище\s*(?:\(\s*NAS\s*\))?\s*(?:NAS)?'
    r'|модуль\s+расширения(?:\s+для\s+сетевого\s+хранилища)?',
    re.IGNORECASE,
)


def extract_nas_model_code(name: str, brand: str = '') -> str:
    return _generic_brand_model_extractor(name, brand, _NAS_PREFIX_RE)


# Кулера CPU: "Устройство охлаждения (кулер) Aerocool Verkho 2"
_COOLER_PREFIX_RE = re.compile(
    r'устройство\s+охлаждения\s*(?:\(\s*кулер\s*\))?'
    r'|кулер(?:\s+для\s+процессора)?'
    r'|система\s+водяного\s+охлаждения'
    r'|\bСВО\b|водяное\s+охлаждение',
    re.IGNORECASE,
)
_COOLER_NOISE_RE = re.compile(
    r'\b(?:4-pin|3-pin|2-pin|\d+мм|\d+\s*мм|сокет\s+\w+)\b', re.IGNORECASE,
)


def extract_cooler_model_code(name: str, brand: str = '') -> str:
    return _generic_brand_model_extractor(
        name, brand, _COOLER_PREFIX_RE,
        extra_noise_re=_COOLER_NOISE_RE,
    )


# Серверные корпуса: "Корпус для сервера монтируемый в стойку EXEGATE Pro 4U390"
_SERVER_CASE_PREFIX_RE = re.compile(
    r'\b(?:'
    r'корпус\s+для\s+сервера(?:\s+монтируемый\s+в\s+стойку)?|'
    r'серверный\s+корпус|'
    r'(?:rack|tower)\s+корпус\s+для\s+сервера'
    r')\b',
    re.IGNORECASE,
)
_SERVER_CASE_NOISE_RE = re.compile(
    # Удаляем только "одиночные" форм-факторы (1U, 2U) без цифр после
    # (4U390 — это часть модели, не оставляем).
    r'\b(?:1U|2U|3U|4U|5U)\s'
    r'|\b\d+\s*Вт\b|\b\d+\s*W\b'
    r'|\b(?:Micro-?ATX|Mini-?DTX|Mini-?ITX|Standard-?ATX|ATX|EATX)\b',
    re.IGNORECASE,
)


def extract_server_case_model_code(name: str, brand: str = '') -> str:
    return _generic_brand_model_extractor(
        name, brand, _SERVER_CASE_PREFIX_RE,
        extra_noise_re=_SERVER_CASE_NOISE_RE,
    )


# ═══════════════════════════════════════════════════════════════════════════
# ЭТАП B: Brand Dictionary для периферии (мыши/клавиатуры/корпуса)
# ═══════════════════════════════════════════════════════════════════════════
# Собрано из реальных данных БД (наиболее частые бренды с 5+ товаров).
# Используется когда нормализатор не может извлечь бренд автоматически
# (например китайские/малоизвестные производители).

PERIPHERAL_BRANDS: frozenset[str] = frozenset({
    # Известные мировые бренды
    'logitech', 'razer', 'corsair', 'steelseries', 'hyperx', 'cougar',
    'thermaltake', 'cooler-master', 'cooler', 'asus', 'msi', 'lenovo',
    'hp', 'dell', 'acer', 'xiaomi', 'apple', 'samsung', 'sony',
    'jbl', 'sennheiser', 'sennheizer', 'bose', 'anker',

    # Российские/китайские бренды периферии
    'a4tech', 'defender', 'redragon', 'panteon', 'ardor', 'qumo',
    'smartbuy', 'genius', 'oklick', 'sven', 'gembird', 'aceline',
    'jetaccess', 'rapoo', 'aula', 'keyron', 'keychron', 'mchose',
    'ajazz', 'fgg', 'akko', 'glorious', 'gravastar', 'darkflash',
    'jonsbo', 'gamemax', 'powercase', 'xastra', 'montech', 'deepcool',
    'pccooler', 'formula', 'ginzzu', 'inwin', 'chieftec', 'zalman',
    'fractal', 'geometric', 'lian-li', 'lian', 'gamdias', 'ocypus',
    'nakatomi', 'ritmix', 'attack', 'wlmouse', 'ninjutso', 'exegate',
    'edifier', 'jlab', 'urgent', 'hyundai', 'nokia', 'ugreen',
    'dexp', 'ardor-gaming', 'mountain', 'cherry', 'wooting',
})

_PERIPHERAL_NOISE_RE = re.compile(
    r'\b(?:'
    # Тип подключения
    r'беспроводная|проводная|wireless|wired|игровая|gaming|механическая|'
    r'мембранная|оптическая|игровой|тонкий|с\s+подсветкой|'
    # Параметры
    r'\d+\s*dpi|\d+\s*DPI|светодиодный|RGB|кнопки|клавиши|'
    r'USB[-\s]?Type[-\s]?[AC]|USB|Bluetooth|BT|3\.5\s*мм|3,5\s*мм|'
    # Конкретные тех. параметры
    r'клавиш\s*-\s*\d+|кнопок\s*-\s*\d+|Mid-Tower|Mini-Tower|Full-Tower|'
    r'Micro-?ATX|Mini-?ITX|Standard-?ATX|E-?ATX|ATX|компактный|SFF|'
    r'без\s+БП|с\s+БП|БП\s+\d+\s*Вт'
    r')\b',
    re.IGNORECASE,
)


def extract_peripheral_model_code(
    name: str,
    category_prefix_re: re.Pattern[str],
    brand: str = '',
) -> str:
    """Универсальный экстрактор для мышей/клавиатур/корпусов.

    Стратегия:
      1. Удалить префикс категории
      2. Удалить [...] блоки
      3. Найти бренд из PERIPHERAL_BRANDS в начале
      4. Взять 2-3 слова после бренда (это модель)
      5. Удалить шумовые токены

    Примеры:
        'Мышь беспроводная A4Tech Fstyler FG35 белый [...]'
            → 'a4tech fstyler fg35'
        'Клавиатура проводная Defender Avenger GK-412 [механическая, ...]'
            → 'defender avenger gk-412'
        'Корпус MONTECH XR [XR (W)] белый [Mid-Tower, ...]'
            → 'montech xr'
    """
    if not name or not category_prefix_re.search(name):
        return ''
    s = category_prefix_re.sub(' ', name)
    s = _SSD_BRACKET_RE.sub(' ', s)
    s = _PERIPHERAL_NOISE_RE.sub(' ', s)
    s = _GENERIC_NOISE_RE.sub(' ', s)
    s = _WS_RE.sub(' ', s).strip()

    if not s:
        return ''

    tokens = s.split()
    if not tokens:
        return ''

    # Ищем бренд в первых 3 токенах
    found_brand: str = ''
    brand_idx: int = -1
    for i, tok in enumerate(tokens[:3]):
        t_lower = tok.lower().strip(',.;:')
        if t_lower in PERIPHERAL_BRANDS:
            found_brand = t_lower
            brand_idx = i
            break
        # Может быть с дефисами: A-4tech
        t_normalized = t_lower.replace('-', '').replace('_', '')
        for known_brand in PERIPHERAL_BRANDS:
            if known_brand.replace('-', '') == t_normalized:
                found_brand = known_brand
                brand_idx = i
                break
        if found_brand:
            break

    # Если бренд найден — берём бренд + 2-3 следующих токена
    if found_brand and brand_idx >= 0:
        model_tokens = tokens[brand_idx + 1:brand_idx + 4]
        model = ' '.join(model_tokens).lower().strip(',.;:')
        if model:
            return f'{found_brand} {model}'.strip()
        return found_brand

    # Если бренд из словаря не нашёлся — используем brand из БД (если есть)
    # и берём первые 2 токена как модель
    if brand:
        model = ' '.join(tokens[:2]).lower()
        return f'{brand.lower()} {model}'.strip()

    # Совсем нет бренда — берём первые 3 токена
    fallback = ' '.join(tokens[:3]).lower()
    return fallback if len(fallback) >= 3 else ''


# Префиксы категорий для периферии
_MOUSE_PREFIX_RE = re.compile(
    r'\bмышь(?:\s*\+\s*коврик)?\s+(?:беспроводная|проводная)?'
    r'(?:\s*/\s*(?:беспроводная|проводная))?\s*',
    re.IGNORECASE,
)
_KEYBOARD_PREFIX_RE = re.compile(
    r'\bклавиатура\s+(?:проводная|беспроводная|игровая|механическая|мембранная)?'
    r'(?:\s*\+\s*(?:беспроводная|проводная))?\s*',
    re.IGNORECASE,
)
_CASE_PREFIX_RE = re.compile(
    r'\bкорпус(?:\s+(?:ATX|micro-?ATX|Mini-?ITX|для\s+ПК))?\s+',
    re.IGNORECASE,
)


def extract_mouse_model_code(name: str, brand: str = '') -> str:
    return extract_peripheral_model_code(name, _MOUSE_PREFIX_RE, brand)


def extract_keyboard_model_code(name: str, brand: str = '') -> str:
    return extract_peripheral_model_code(name, _KEYBOARD_PREFIX_RE, brand)


def extract_case_model_code(name: str, brand: str = '') -> str:
    return extract_peripheral_model_code(name, _CASE_PREFIX_RE, brand)


# Наушники: "Наушники Xiaomi Redmi Buds 5 Pro, Bluetooth"
_HEADPHONES_PREFIX_RE = re.compile(r'\bнаушники\b|\bгарнитура\b', re.IGNORECASE)
_HEADPHONES_NOISE_RE = re.compile(
    r'\b(?:Bluetooth|BT|3\.5\s*мм|3,5\s*мм|USB[-\s]?Type[-\s]?[AC]|USB|'
    r'внутриканальные|накладные|вкладыши|мониторные|охватывающие|'
    r'TWS|True\s+Wireless|Earbuds)\b',
    re.IGNORECASE,
)


def extract_headphones_model_code(name: str, brand: str = '') -> str:
    return _generic_brand_model_extractor(
        name, brand, _HEADPHONES_PREFIX_RE,
        extra_noise_re=_HEADPHONES_NOISE_RE,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Mapping категорий → экстракторы
# ═══════════════════════════════════════════════════════════════════════════

_CPU_SLUGS = frozenset({'processory', 'servernye-processory'})
_GPU_SLUGS = frozenset({'videokarty'})
_MB_SLUGS = frozenset({'materinskie-platy', 'servernye-materinskie-platy'})
_MONITOR_SLUGS = frozenset({'monitory'})
_PSU_SLUGS = frozenset({'bloki-pitaniya', 'servernye-bloki-pitaniya'})

# Новые: simple-категории
_MEMORY_CARD_SLUGS = frozenset({'karty-pamyati'})
_MIC_SLUGS = frozenset({'mikrofony'})
_SOUNDCARD_SLUGS = frozenset({'zvukovye-karty'})
_EXT_HDD_SLUGS = frozenset({'vneshnie-zhestkie-diski'})
_NAS_SLUGS = frozenset({'setevye-hranilisha'})
_COOLER_SLUGS = frozenset({'ohlazhdenie-dlya-servernyh-processorov'})
_SERVER_CASE_SLUGS = frozenset({'servernye-korpusa'})
_HEADPHONES_SLUGS = frozenset({'naushniki'})

# Этап B: периферия с brand dictionary
_MOUSE_SLUGS = frozenset({'myshi'})
_KEYBOARD_SLUGS = frozenset({'klaviatury'})
_CASE_SLUGS = frozenset({'korpusa'})


def _model_code_for_category(
    name: str, brand: str, vendor_code: str, slug: str,
) -> str:
    if slug in _SSD_LIKE_SLUGS:
        return extract_ssd_model_code(name, brand=brand, mpn=vendor_code)
    prefix_re = _DEVICE_PREFIX_RE.get(slug)
    if prefix_re is not None:
        return extract_device_model_code(name, brand='', prefix_re=prefix_re)
    if slug in _RAM_SLUGS:
        return extract_ram_model_code(name, brand=brand)
    # Этап B: расширенные экстракторы (CPU, GPU, MB, Monitor, PSU)
    if slug in _CPU_SLUGS:
        return extract_cpu_model_code(name, brand=brand)
    if slug in _GPU_SLUGS:
        return extract_gpu_model_code(name, brand=brand)
    if slug in _MB_SLUGS:
        return extract_mb_model_code(name, brand=brand)
    if slug in _MONITOR_SLUGS:
        return extract_monitor_model_code(name, brand=brand)
    if slug in _PSU_SLUGS:
        return extract_psu_model_code(name, brand=brand)
    # Этап A: новые simple-категории
    if slug in _MEMORY_CARD_SLUGS:
        return extract_memory_card_model_code(name, brand=brand)
    if slug in _MIC_SLUGS:
        return extract_microphone_model_code(name, brand=brand)
    if slug in _SOUNDCARD_SLUGS:
        return extract_soundcard_model_code(name, brand=brand)
    if slug in _EXT_HDD_SLUGS:
        return extract_ext_hdd_model_code(name, brand=brand)
    if slug in _NAS_SLUGS:
        return extract_nas_model_code(name, brand=brand)
    if slug in _COOLER_SLUGS:
        return extract_cooler_model_code(name, brand=brand)
    if slug in _SERVER_CASE_SLUGS:
        return extract_server_case_model_code(name, brand=brand)
    if slug in _HEADPHONES_SLUGS:
        return extract_headphones_model_code(name, brand=brand)
    # Этап B: периферия с brand dictionary
    if slug in _MOUSE_SLUGS:
        return extract_mouse_model_code(name, brand=brand)
    if slug in _KEYBOARD_SLUGS:
        return extract_keyboard_model_code(name, brand=brand)
    if slug in _CASE_SLUGS:
        return extract_case_model_code(name, brand=brand)
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
