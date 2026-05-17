
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import Category, Offer, Product

logger = logging.getLogger(__name__)


_BRACKET_MPN_RE = re.compile(r'\[([A-Za-z0-9][A-Za-z0-9\-_/.]{3,})\]')

_PUNCT_RE = re.compile(r'[^\w\s]', flags=re.UNICODE)
_WS_RE = re.compile(r'\s+')

_NUM_RE = re.compile(r'\d+')


_NUM_DISCRIMINATE_MIN = 100


def _normalize_name(name: str) -> str:
    s = (name or '').lower()
    s = _PUNCT_RE.sub(' ', s)
    s = _WS_RE.sub(' ', s).strip()
    return s


def _tokens(name: str) -> set[str]:
    return {t for t in _normalize_name(name).split() if len(t) > 1}


def _dice(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    total = len(a) + len(b)
    return (2 * inter) / total if total else 0.0


def _extract_mpn_from_name(name: str) -> str:
    if not name:
        return ''
    for match in _BRACKET_MPN_RE.finditer(name):
        code = (match.group(1) or '').strip()

        if len(code) >= 4 and any(ch.isdigit() for ch in code) and any(ch.isalpha() for ch in code):
            return code.upper()
    return ''


def _significant_numbers(name: str) -> set[int]:
    if not name:
        return set()
    nums: set[int] = set()
    for m in _NUM_RE.findall(name):
        try:
            n = int(m)
        except ValueError:
            continue
        if n >= _NUM_DISCRIMINATE_MIN:
            nums.add(n)
    return nums


def _numbers_contradict(name_a: str, name_b: str) -> bool:
    a = _significant_numbers(name_a)
    b = _significant_numbers(name_b)
    if not a or not b:
        return False
    return bool(a - b) and bool(b - a)


def normalize_offer_url(url: str, source: str = '') -> str:
    from .dedupe.normalizer import normalize_offer_url as _norm

    return _norm(url, source=source)


@dataclass
class MatchResult:
    product: Product
    created: bool
    reason: str


def _match_threshold() -> float:
    return float(getattr(settings, 'PRODUCT_MATCH_THRESHOLD', 0.62))


def _find_by_mpn(category: Category, mpn: str, *, candidate_name: str = '') -> Product | None:
    if not mpn:
        return None
    mpn_norm = mpn.strip().upper()
    if not mpn_norm:
        return None
    candidates = list(
        Product.objects
        .filter(category=category, vendor_code__iexact=mpn_norm)
        .only('id', 'name', 'vendor_code')[:10]
    )
    for candidate in candidates:
        if candidate_name and _numbers_contradict(candidate_name, candidate.name):
            logger.warning(
                'MPN=%s совпал у "%s" и "%s", но числа противоречат — разные товары',
                mpn_norm, candidate_name, candidate.name,
            )
            continue
        return candidate
    return None


def _find_by_name(category: Category, name: str) -> Product | None:
    if not name:
        return None
    target = _tokens(name)
    if len(target) < 2:
        return None


    anchor = max(target, key=len)
    if len(anchor) < 3:
        anchor = ''

    qs = Product.objects.filter(category=category)
    if anchor:
        qs = qs.filter(name__icontains=anchor)

    best: tuple[float, Product | None] = (0.0, None)
    threshold = _match_threshold()
    for candidate in qs.only('id', 'name')[:500]:
        if _numbers_contradict(name, candidate.name):
            continue
        score = _dice(target, _tokens(candidate.name))
        if score > best[0]:
            best = (score, candidate)
    if best[1] is not None and best[0] >= threshold:
        logger.debug(
            'Product match by name: "%s" ~ "%s" (dice=%.2f)',
            name, best[1].name, best[0],
        )
        return best[1]
    return None


def _looks_like_mpn(value: str) -> bool:
    v = (value or '').strip()
    if len(v) < 4:
        return False
    if v.isdigit():
        return False
    return any(ch.isalpha() for ch in v) and any(ch.isdigit() for ch in v)


def match_or_create_product(
    *,
    category: Category,
    name: str,
    vendor_code: str = '',
    image_url: str = '',
    fallback_url: str = '',
    mpn_hint: str = '',
) -> MatchResult:
    hint = (mpn_hint or '').strip()
    if not hint and _looks_like_mpn(vendor_code):
        hint = vendor_code.strip()
    mpn = hint.upper() or _extract_mpn_from_name(name)

    if mpn:
        existing = _find_by_mpn(category, mpn, candidate_name=name)
        if existing:
            _touch_product(existing, name=name, image_url=image_url, mpn=mpn)
            return MatchResult(product=existing, created=False, reason='mpn')

    existing = _find_by_name(category, name)
    if existing:
        _touch_product(existing, name=name, image_url=image_url, mpn=mpn)
        return MatchResult(product=existing, created=False, reason='name')


    try:
        with transaction.atomic():
            product = Product.objects.create(
                name=name,
                slug=_make_unique_slug(name, mpn, fallback_url),
                category=category,
                vendor_code=mpn,
                url=fallback_url or '',
                image_url=image_url or '',
                is_active=True,
                last_parsed_at=timezone.now(),
            )
    except IntegrityError:
        existing = None
        if mpn:
            existing = _find_by_mpn(category, mpn, candidate_name=name)
        if existing is None:
            existing = _find_by_name(category, name)
        if existing is not None:
            logger.info(
                'Гонка при создании Product mpn=%s, имя=%r — подтянули существующий id=%d',
                mpn or '—', name[:80], existing.pk,
            )
            _touch_product(existing, name=name, image_url=image_url, mpn=mpn)
            return MatchResult(product=existing, created=False, reason='mpn' if mpn else 'name')

        raise
    logger.info(
        'Создан мастер-товар: %s (id=%d, mpn=%s)',
        product.name, product.pk, mpn or '—',
    )
    return MatchResult(product=product, created=True, reason='new')


def _touch_product(
    product: Product,
    *,
    name: str,
    image_url: str,
    mpn: str,
) -> None:
    updates: list[str] = []
    if not product.name and name:
        product.name = name[:512]
        updates.append('name')
    if image_url and not product.image_url:
        product.image_url = image_url[:1024]
        updates.append('image_url')
    mpn_norm = (mpn or '').strip().upper()
    current_vc = (product.vendor_code or '').strip()
    if mpn_norm and _looks_like_mpn(mpn_norm):
        if not current_vc or current_vc.isdigit():
            product.vendor_code = mpn_norm[:100]
            updates.append('vendor_code')
    product.last_parsed_at = timezone.now()
    updates.extend(['last_parsed_at', 'updated_at'])
    product.save(update_fields=list(dict.fromkeys(updates)))


@dataclass
class OfferUpsertResult:
    offer: Offer
    offer_created: bool
    product_created: bool
    match_reason: str


def upsert_offer(
    *,
    category: Category,
    source: str,
    name: str,
    url: str,
    vendor_code: str = '',
    image_url: str = '',
    is_available: bool = True,
) -> OfferUpsertResult:
    if _v2_enabled():
        from .dedupe.services import upsert_offer as v2_upsert

        v2_res = v2_upsert(
            category=category,
            source=source,
            name=name,
            url=url,
            vendor_code=vendor_code,
            image_url=image_url,
            is_available=is_available,
        )
        return OfferUpsertResult(
            offer=v2_res.offer,
            offer_created=v2_res.offer_created,
            product_created=v2_res.product_created,
            match_reason=v2_res.match_reason,
        )

    if _shadow_enabled():

        try:
            from .dedupe.services import shadow_match

            shadow_match(
                category=category,
                source=source,
                name=name,
                url=url,
                vendor_code=vendor_code,
            )
        except Exception:
            logger.exception('shadow_match v2 не отработал, продолжаем legacy upsert')

    return _legacy_upsert_offer(
        category=category, source=source, name=name, url=url,
        vendor_code=vendor_code, image_url=image_url, is_available=is_available,
    )


def _v2_enabled() -> bool:
    return bool(getattr(settings, 'DEDUP_V2', False))


def _shadow_enabled() -> bool:
    return bool(getattr(settings, 'DEDUP_SHADOW', False))


def _legacy_update_existing_offer(
    offer: Offer,
    *,
    name: str,
    vendor_code: str,
    image_url: str,
    is_available: bool,
) -> OfferUpsertResult:
    changed: list[str] = []
    if image_url and offer.image_url != image_url:
        offer.image_url = image_url[:1024]
        changed.append('image_url')
    if vendor_code and offer.vendor_code != vendor_code:
        offer.vendor_code = vendor_code[:128]
        changed.append('vendor_code')
    if offer.is_available != is_available:
        offer.is_available = is_available
        changed.append('is_available')
    offer.last_seen_at = timezone.now()
    changed.extend(['last_seen_at', 'updated_at'])
    offer.save(update_fields=list(dict.fromkeys(changed)))
    _touch_product(
        offer.product, name=name, image_url=image_url,
        mpn=_extract_mpn_from_name(name),
    )
    return OfferUpsertResult(
        offer=offer,
        offer_created=False,
        product_created=False,
        match_reason='existing',
    )


@transaction.atomic
def _legacy_upsert_offer(
    *,
    category: Category,
    source: str,
    name: str,
    url: str,
    vendor_code: str = '',
    image_url: str = '',
    is_available: bool = True,
) -> OfferUpsertResult:
    src = (source or '').lower()
    canonical_url = normalize_offer_url(url, source=src) or url

    offer = (
        Offer.objects
        .filter(source=src, url=canonical_url)
        .select_related('product')
        .first()
    )
    if offer:
        return _legacy_update_existing_offer(
            offer, name=name, vendor_code=vendor_code,
            image_url=image_url, is_available=is_available,
        )

    match = match_or_create_product(
        category=category,
        name=name,
        vendor_code=vendor_code,
        image_url=image_url,
        fallback_url=canonical_url,
    )


    try:
        with transaction.atomic():
            offer = Offer.objects.create(
                product=match.product,
                source=src,
                url=canonical_url,
                vendor_code=vendor_code[:128] if vendor_code else '',
                image_url=image_url[:1024] if image_url else '',
                is_available=is_available,
                last_seen_at=timezone.now(),
            )
    except IntegrityError:
        existing = (
            Offer.objects
            .filter(source=src, url=canonical_url)
            .select_related('product')
            .first()
        )
        if existing is None:


            raise
        logger.info(
            'Гонка при создании оффера (%s, %s) — подтянули существующий id=%d',
            src, canonical_url, existing.pk,
        )
        return _legacy_update_existing_offer(
            existing, name=name, vendor_code=vendor_code,
            image_url=image_url, is_available=is_available,
        )

    logger.info(
        'Создан оффер %s для товара "%s" (product_id=%d, match=%s)',
        src, match.product.name, match.product.pk, match.reason,
    )
    return OfferUpsertResult(
        offer=offer,
        offer_created=True,
        product_created=match.created,
        match_reason=match.reason,
    )


def get_or_create_offer(
    *,
    category: Category,
    source: str,
    name: str,
    url: str,
    vendor_code: str = '',
    image_url: str = '',
    is_available: bool = True,
) -> tuple[Offer, bool]:
    res = upsert_offer(
        category=category,
        source=source,
        name=name,
        url=url,
        vendor_code=vendor_code,
        image_url=image_url,
        is_available=is_available,
    )
    return res.offer, res.offer_created


def get_or_create_product(
    category: Category,
    name: str,
    url: str,
    vendor_code: str = '',
    image_url: str = '',
) -> tuple[Product, bool]:
    match = match_or_create_product(
        category=category,
        name=name,
        vendor_code=vendor_code,
        image_url=image_url,
        fallback_url=normalize_offer_url(url) or url,
    )
    return match.product, match.created


def _make_unique_slug(name: str, vendor_code: str, url: str) -> str:
    base = slugify(name, allow_unicode=True)[:420]
    url_key = hashlib.sha256((url or '').encode('utf-8')).hexdigest()[:12]
    vc = slugify(vendor_code, allow_unicode=True)[:80] if vendor_code else ''
    parts = [p for p in (base, vc, url_key) if p]
    slug = '-'.join(parts)[:500] or url_key
    n = 0
    while Product.objects.filter(slug=slug).exists():
        n += 1
        slug = f'{slug[:480]}-d{n}'[:512]
    return slug


def bulk_update_products(parsed_items: list[dict[str, Any]], category: Category) -> list[Product]:
    products: list[Product] = []
    for item in parsed_items:
        product, _ = get_or_create_product(
            category=category,
            name=item['name'],
            url=item['url'],
            vendor_code=item.get('vendor_code', ''),
            image_url=item.get('image_url', ''),
        )
        products.append(product)
    return products


__all__: Iterable[str] = (
    'MatchResult',
    'OfferUpsertResult',
    'bulk_update_products',
    'get_or_create_offer',
    'get_or_create_product',
    'match_or_create_product',
    'normalize_offer_url',
    'upsert_offer',
)
