from __future__ import annotations

import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .constants import (
    BRAND_ALIASES,
    COLORS,
    CPU_FAMILIES,
    GPU_FAMILIES,
    RE_BRACKET_MPN,
)
from .features import Features

logger = logging.getLogger(__name__)


_PUNCT_RE = re.compile(r'[^\w\s/]', flags=re.UNICODE)

_WS_RE = re.compile(r'\s+')

_FREE_MPN_RE = re.compile(
    r'(?<![A-Za-z0-9])'
    r'([A-Za-z]{1,4}\d{2,}[A-Za-z0-9\-_/]*'
    r'|\d{2,}[A-Za-z]{1,4}\d{1,}[A-Za-z0-9\-_/]*)'
    r'(?![A-Za-z0-9])',
)
_BRACKET_MPN_RE = re.compile(RE_BRACKET_MPN)


def _strip_accents(s: str) -> str:
    if not s:
        return ''
    return unicodedata.normalize('NFC', s).lower().strip()


def _normalize_name(name: str) -> str:
    s = (name or '').lower()
    s = _PUNCT_RE.sub(' ', s)
    s = _WS_RE.sub(' ', s).strip()
    return s


def _tokens(name: str) -> set[str]:
    return {t for t in _normalize_name(name).split() if len(t) > 1 and t != '/'}


def _looks_like_mpn(value: str) -> bool:
    v = (value or '').strip()
    if len(v) < 4:
        return False
    if v.isdigit():
        return False

    has_latin = any('a' <= ch.lower() <= 'z' for ch in v)
    if not has_latin:
        return False
    has_digit = any(ch.isdigit() for ch in v)
    has_separator = any(ch in '-_/' for ch in v)
    if not (has_digit or has_separator):
        return False

    head, sep, _ = v.partition('-')
    if sep and head.isalpha() and len(head) <= 3 and head.lower() in {'id', 'wb', 'sku'}:
        return False
    return True


def _normalize_mpn(value: str) -> str:
    if not value:
        return ''
    return ''.join(ch for ch in value.strip() if not ch.isspace()).upper()


_BRAND_BY_ALIAS: dict[str, str] = {}
for canonical, aliases in BRAND_ALIASES.items():
    for alias in aliases:
        _BRAND_BY_ALIAS[alias.lower()] = canonical

_BRAND_ALIASES_SORTED: list[str] = sorted(_BRAND_BY_ALIAS.keys(), key=len, reverse=True)


def extract_brand(name: str) -> str:
    if not name:
        return ''
    n = _strip_accents(name)
    n_padded = f' {n} '
    for alias in _BRAND_ALIASES_SORTED:


        if f' {alias} ' in n_padded:
            return _BRAND_BY_ALIAS[alias]
    return ''


def _extract_mpn_from_brackets(name: str) -> str:
    if not name:
        return ''
    for match in _BRACKET_MPN_RE.finditer(name):
        code = (match.group(1) or '').strip()
        if _looks_like_mpn(code):
            return _normalize_mpn(code)
    return ''


def _extract_mpn_freeform(name: str) -> str:
    if not name:
        return ''
    candidates: list[str] = []
    for match in _FREE_MPN_RE.finditer(name):
        token = match.group(1)
        if not _looks_like_mpn(token):
            continue


        if len(token) < 6:
            continue
        candidates.append(token)
    if not candidates:
        return ''
    candidates.sort(key=lambda x: (len(x), sum(ch.isdigit() for ch in x)), reverse=True)
    return _normalize_mpn(candidates[0])


def _extract_mpn_from_url(url: str) -> str:
    if not url:
        return ''
    try:
        path = urlparse(url).path or ''
    except Exception:
        return ''
    for segment in re.split(r'[/_\-]', path):
        if _looks_like_mpn(segment) and len(segment) >= 7:
            return _normalize_mpn(segment)
    return ''


def extract_mpn(
    name: str,
    *,
    sku: str = '',
    url: str = '',
    hint: str = '',
) -> tuple[str, str]:
    h = (hint or '').strip()
    if h and _looks_like_mpn(h):
        return _normalize_mpn(h), 'mpn_hint'

    bracket = _extract_mpn_from_brackets(name)
    if bracket:
        return bracket, 'bracket'

    free = _extract_mpn_freeform(name)
    s = (sku or '').strip()
    sku_norm = _normalize_mpn(s) if (s and _looks_like_mpn(s) and len(s) >= 6) else ''


    if sku_norm and free:
        if free.startswith(sku_norm) and len(free) > len(sku_norm):
            return free, 'name'
        if sku_norm.startswith(free) and len(sku_norm) > len(free):
            return sku_norm, 'sku'

    if sku_norm:
        return sku_norm, 'sku'

    if free:
        return free, 'name'

    from_url = _extract_mpn_from_url(url)
    if from_url:
        return from_url, 'url'

    return '', ''


_RE_NUM_UNIT = re.compile(
    r'(\d{1,4})\s*(гб|gb|тб|tb)(?![a-zа-я])',
    flags=re.IGNORECASE,
)

_NUM_UNIT_TAIL_LEN = 30


_RAM_MARKERS = ('ddr3', 'ddr4', 'ddr5', 'lpddr', 'озу', 'оперативн', 'ram', 'память')

_STORAGE_MARKERS = (
    'ssd', 'nvme', 'm.2', 'm2', 'hdd', 'жест', 'жёст', 'накопит', 'emmc',
)

_RE_SCREEN = re.compile(
    r'(\d{1,2}(?:[.,]\d)?)\s*(?:["”″`\']|inch|inches|in|"|дюйм)',
    flags=re.IGNORECASE,
)

_RE_YEAR = re.compile(r'\b(20\d{2})\b')


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _to_decimal(value: str) -> Decimal | None:
    if value is None:
        return None
    s = str(value).replace(',', '.').strip()
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    if d < 0 or d > 100:

        return None
    return d


def _classify_num_unit(name: str) -> tuple[int | None, int | None]:
    matches = list(_RE_NUM_UNIT.finditer(name))
    if not matches:
        return None, None
    ram: int | None = None
    storage: int | None = None
    for idx, m in enumerate(matches):
        n = _to_int(m.group(1))
        if n is None:
            continue
        unit = m.group(2).lower()


        tail_end = m.end() + _NUM_UNIT_TAIL_LEN
        if idx + 1 < len(matches):
            tail_end = min(tail_end, matches[idx + 1].start())
        tail = name[m.end(): tail_end].lower()

        is_tb = unit in ('тб', 'tb')
        has_storage_marker = any(kw in tail for kw in _STORAGE_MARKERS)
        has_ram_marker = any(kw in tail for kw in _RAM_MARKERS)

        if is_tb:
            value = n * 1024
            if 1 <= value <= 32 * 1024 and storage is None:
                storage = value
            continue

        if has_storage_marker:
            if 1 <= n <= 32 * 1024 and storage is None:
                storage = n
            continue
        if has_ram_marker:
            if 1 <= n <= 256 and ram is None:
                ram = n
            continue


        if 4 <= n <= 128 and ram is None:
            ram = n
        elif n >= 128 and storage is None:
            storage = n
    return ram, storage


def _extract_ram_gb(name: str) -> int | None:
    if not name:
        return None
    return _classify_num_unit(name)[0]


def _extract_storage_gb(name: str) -> int | None:
    if not name:
        return None
    return _classify_num_unit(name)[1]


def _extract_screen_in(name: str) -> Decimal | None:
    if not name:
        return None
    m = _RE_SCREEN.search(name)
    if not m:
        return None
    d = _to_decimal(m.group(1))
    if d is None:
        return None
    if d < Decimal('5') or d > Decimal('60'):
        return None
    return d


def _extract_cpu_family(name: str) -> str:
    n = _strip_accents(name)
    n = re.sub(r'[^\w\s\-]', ' ', n)
    n = _WS_RE.sub(' ', n)
    for fam in CPU_FAMILIES:
        if fam in n:
            return fam
    if 'apple' in n or 'macbook' in n:
        m = re.search(r'\bm([1-9])\b', n)
        if m:
            return f'apple m{m.group(1)}'
    return ''


def _extract_gpu_family(name: str) -> str:
    n = _strip_accents(name)
    n = re.sub(r'[^\w\s\-]', ' ', n)
    n = _WS_RE.sub(' ', n)
    for fam in GPU_FAMILIES:
        if fam in n:
            return fam
    return ''


def _extract_color(name: str) -> str:
    n = _strip_accents(name)
    for c in COLORS:
        c_norm = _strip_accents(c)

        if re.search(rf'\b{re.escape(c_norm)}\b', n):
            return c_norm
    return ''


def _extract_year(name: str) -> int | None:
    if not name:
        return None
    m = _RE_YEAR.search(name)
    if not m:
        return None
    y = _to_int(m.group(1))
    if y is None or not (2010 <= y <= 2030):
        return None
    return y


def extract_specs(name: str) -> dict[str, Any]:
    out: dict[str, Any] = {}

    ram = _extract_ram_gb(name)
    if ram is not None:
        out['ram_gb'] = ram

    storage = _extract_storage_gb(name)
    if storage is not None:
        out['storage_gb'] = storage

    screen = _extract_screen_in(name)
    if screen is not None:
        out['screen_in'] = str(screen)

    cpu = _extract_cpu_family(name)
    if cpu:
        out['cpu_family'] = cpu

    gpu = _extract_gpu_family(name)
    if gpu:
        out['gpu_family'] = gpu

    color = _extract_color(name)
    if color:
        out['color'] = color

    year = _extract_year(name)
    if year is not None:
        out['year'] = year

    return out


_VARIANT_QUERY_KEYS: frozenset[str] = frozenset({
    'config', 'configuration', 'variant', 'variantid', 'variant_id',
    'offer', 'offer_id', 'offerid', 'sku', 'memory', 'ram', 'storage', 'ssd',
})

_UTM_QUERY_PREFIXES = ('utm_', 'ref', 'from', 'yclid', 'gclid', 'fbclid', 'mc_')
_UTM_QUERY_EXACT = frozenset({'utm', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'ref', 'from', 'source'})


def _is_tracking_query_key(key: str) -> bool:
    low = key.lower()
    if low in _UTM_QUERY_EXACT:
        return True
    return any(low.startswith(p) for p in _UTM_QUERY_PREFIXES)


def _variant_query_items(query: dict[str, list[str]]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for key in sorted(query.keys()):
        low = key.lower()
        if low in _VARIANT_QUERY_KEYS:
            vals = query.get(key) or []
            if vals and str(vals[0]).strip():
                items.append((low, str(vals[0]).strip()))
    return items


def extract_variant_from_url(url: str) -> tuple[str, dict[str, Any]]:
    if not url:
        return '', {}
    try:
        u = urlparse(url.strip())
        q = parse_qs(u.query, keep_blank_values=True)
    except Exception:
        return '', {}
    items = _variant_query_items(q)
    if not items:
        return '', {}
    label = ', '.join(f'{k}={v}' for k, v in items)
    specs_patch: dict[str, Any] = {'variant_key': label}
    blob = ' '.join(v for _, v in items).lower()
    ram_m = re.search(r'(\d{1,3})\s*(?:gb|гб)\s*(?:ram|озу|памят)', blob)
    if not ram_m:
        ram_m = re.search(r'(\d{1,3})\s*(?:gb|гб)', blob)
    if ram_m:
        try:
            specs_patch['ram_gb'] = int(ram_m.group(1))
        except ValueError:
            pass
    ssd_m = re.search(r'(\d{3,4})\s*(?:gb|гб|tb|тб)', blob)
    if ssd_m:
        try:
            val = int(ssd_m.group(1))
            if val >= 128:
                specs_patch['storage_gb'] = val if val < 10000 else val
        except ValueError:
            pass
    return label, specs_patch


def normalize_offer_url(url: str, source: str = '') -> str:
    if not url:
        return ''
    try:
        u = urlparse(url.strip())
        if not u.scheme or not u.netloc:
            return url
        path = (u.path or '/').rstrip('/') or '/'
        q = parse_qs(u.query, keep_blank_values=True)
        keep_variant = (source or '').lower() == 'citilink' or bool(_variant_query_items(q))
        if keep_variant:
            variant_items = _variant_query_items(q)
            clean_q: dict[str, list[str]] = {k: [v] for k, v in variant_items}
            query = urlencode(clean_q, doseq=True) if clean_q else ''
        else:
            query = ''
        return urlunparse((u.scheme, u.netloc.lower(), path, '', query, ''))
    except Exception:
        return url


def normalize_offer(
    *,
    name: str,
    source: str,
    category_id: int | None,
    sku: str = '',
    url: str = '',
    mpn_hint: str = '',
) -> Features:
    brand = extract_brand(name)
    mpn, mpn_src = extract_mpn(name, sku=sku, url=url, hint=mpn_hint)
    specs = extract_specs(name)
    variant_label, variant_specs = extract_variant_from_url(url)
    if variant_specs:
        for k, v in variant_specs.items():
            if k not in specs or specs.get(k) in (None, ''):
                specs[k] = v
    clean = _normalize_name(name)
    tokens = frozenset(t for t in clean.split() if len(t) > 1)
    return Features(
        brand=brand,
        model_code=mpn,
        model_code_source=mpn_src,
        specs=specs,
        clean_name=clean,
        tokens=tokens,
        source=(source or '').lower(),
        category_id=category_id,
        source_sku=(sku or '').strip(),
    )


def dice(a: Iterable[str], b: Iterable[str]) -> float:
    sa = set(a) if not isinstance(a, set) else a
    sb = set(b) if not isinstance(b, set) else b
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    total = len(sa) + len(sb)
    return (2 * inter) / total if total else 0.0


def specs_contradict(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if not a or not b:
        return False
    for key in ('ram_gb', 'storage_gb', 'screen_in', 'model_code', 'variant_key'):
        va = a.get(key)
        vb = b.get(key)
        if va in (None, '') or vb in (None, ''):
            continue
        if str(va) != str(vb):
            return True
    return False


__all__ = (
    'Features',
    'dice',
    'extract_brand',
    'extract_mpn',
    'extract_specs',
    'normalize_offer',
    'normalize_offer_url',
    'extract_variant_from_url',
    'specs_contradict',
)
