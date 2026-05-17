
from __future__ import annotations

import logging
import random
import re
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.conf import settings

from apps.products.dedupe.normalizer import extract_variant_from_url

from .base_parser import BaseParser
from .parsers import ChromeDriverMixin, ParsedProduct

logger = logging.getLogger(__name__)

CITILINK_HOST = 'www.citilink.ru'
CITILINK_BASE = 'https://www.citilink.ru'

_CITILINK_CARDS_EXTRACT_JS = r"""
return (function () {
  function cleanInt(raw) {
    if (raw == null) return null;
    var s = String(raw).replace(/\s+/g, '').replace(/[^\d]/g, '');
    return /^\d+$/.test(s) ? parseInt(s, 10) : null;
  }
  function cardIsAvailable(card) {
    var t = (card.innerText || '').toLowerCase();
    if (t.indexOf('нет в наличии') !== -1) return false;
    if (t.indexOf('нет в продаже') !== -1) return false;
    if (t.indexOf('недоступен') !== -1 && t.indexOf('заказ') === -1) return false;
    if (t.indexOf('сообщить о поступлении') !== -1) return false;
    if (t.indexOf('уведомить о поступлении') !== -1) return false;
    return true;
  }
  function firstSrcFromSet(raw) {
    if (!raw) return '';
    var chunk = String(raw).split(',')[0] || '';
    var url = chunk.trim().split(/\s+/)[0] || '';
    return url.trim();
  }
  function normalizeImgUrl(url) {
    if (!url) return '';
    var u = String(url).trim();
    if (!u) return '';
    if (u.indexOf('data:') === 0 || u.indexOf('blob:') === 0) return '';
    if (u.indexOf('//') === 0) return 'https:' + u;
    if (u.indexOf('/') === 0) return 'https://www.citilink.ru' + u;
    return u;
  }
  var cards = document.querySelectorAll(
    '[data-meta-name="ProductHorizontalSnippet"],[data-meta-name="ProductVerticalSnippet"]'
  );
  var out = [];
  var seen = Object.create(null);
  for (var i = 0; i < cards.length; i++) {
    var card = cards[i];
    var pe = card.querySelector('[data-meta-price]');
    if (!pe) continue;
    var price = cleanInt(pe.getAttribute('data-meta-price'));
    if (price == null || price <= 0) continue;
    var a = card.querySelector('a[href*="/product/"]');
    if (!a) continue;
    var href = a.href || a.getAttribute('href') || '';
    if (href && href.indexOf('http') !== 0) {
      href = 'https://www.citilink.ru' + (href.charAt(0) === '/' ? href : '/' + href);
    }
    if (!href) continue;
    var variantHint = '';
    var cfgEl = card.querySelector(
      '[data-meta-name*="Configuration"],[data-meta-name*="Variant"],[data-meta-configuration]'
    );
    if (cfgEl) {
      variantHint = (cfgEl.getAttribute('data-meta-configuration') || cfgEl.innerText || '').trim();
    }
    var name = (a.getAttribute('title') || a.innerText || '').trim();
    if (!name) continue;
    if (variantHint && name.indexOf(variantHint) === -1) {
      name = name + ' [' + variantHint + ']';
    }
    var oldPrice = null;
    var oldWrap = card.querySelector('[data-meta-is-old-price="true"]');
    if (oldWrap) {
      var op = oldWrap.querySelector('[data-meta-price]');
      if (op) oldPrice = cleanInt(op.getAttribute('data-meta-price'));
    }
    var img = card.querySelector('img, picture img, picture source');
    var imageUrl = '';
    if (img) {
      imageUrl =
        img.getAttribute('data-src') ||
        img.getAttribute('src') ||
        firstSrcFromSet(img.getAttribute('data-srcset')) ||
        firstSrcFromSet(img.getAttribute('srcset')) ||
        '';
      imageUrl = normalizeImgUrl(imageUrl);
    }
    var offerSku = '';
    var skuEl = card.querySelector('[data-meta-product-id],[data-meta-offer-id]');
    if (skuEl) {
      offerSku = skuEl.getAttribute('data-meta-product-id')
        || skuEl.getAttribute('data-meta-offer-id') || '';
    }
    seen[href] = true;
    out.push({
      name: name,
      url: href,
      price: price,
      old_price: oldPrice,
      image_url: imageUrl,
      vendor_code: offerSku,
      is_available: cardIsAvailable(card)
    });
  }
  return out;
})();
"""

_PAGES_COUNT_JS = r"""
var el = document.querySelector('[data-meta-name="SubcategoryPageTitle__product-count"]');
if (!el) return 1;
var cnt = el.getAttribute('data-meta-product-count');
if (!cnt) return 1;
var n = parseInt(cnt, 10);
if (!n || n < 1) return 1;
return Math.max(1, Math.ceil(n / 48));
"""


def _normalize_catalog_url(path: str) -> str:
    p = (path or '').strip()
    if not p:
        return ''
    if p.startswith('http://') or p.startswith('https://'):
        u = urlparse(p)
        path_only = (u.path or '/').rstrip('/') or '/'
        host = u.netloc or CITILINK_HOST
    else:
        left = p.lstrip('/').rstrip('/')
        path_only = '/' + left
        host = CITILINK_HOST
    if '/catalog/' not in path_only:
        path_only = '/catalog' + path_only
    path_only = path_only.rstrip('/') or '/'
    return urlunparse(('https', host, path_only, '', '', ''))


def _with_page_and_city(base_url: str, page: int, city_code: str) -> str:
    u = urlparse(base_url)
    q = parse_qs(u.query, keep_blank_values=True)
    q['p'] = [str(max(1, int(page)))]
    if city_code:
        q['action'] = ['changeCity']
        q['space'] = [city_code]
    else:
        q.pop('action', None)
        q.pop('space', None)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q, doseq=True), u.fragment))


def _vendor_code_from_url(url: str) -> str:
    m = re.search(r'-(\d{5,})(?:/|\?|$)', url)
    return m.group(1) if m else ''


class CitilinkParser(ChromeDriverMixin, BaseParser):

    def __init__(self) -> None:
        self._init_chrome_runtime(
            page_timeout_setting='CITILINK_PAGE_LOAD_TIMEOUT',
            page_timeout_default=getattr(settings, 'DNS_PAGE_LOAD_TIMEOUT', 90),
            headless_setting='CITILINK_HEADLESS',
            headless_default=False,
            user_data_dir_setting='CITILINK_USER_DATA_DIR',
        )
        self.catalog_element_wait = int(getattr(settings, 'CITILINK_CATALOG_ELEMENT_WAIT', 45))
        self._city_code = (getattr(settings, 'CITILINK_CITY_CODE', '') or '').strip()
        self._max_pages = int(getattr(settings, 'CITILINK_MAX_PAGES', 80))
        self._warmed_up = False

    @staticmethod
    def _check_blocked(driver: Any) -> None:
        title, url, src = '', '', ''
        try:
            title = (driver.title or '').strip()
            url = (driver.current_url or '').strip()
            src = (driver.page_source or '')[:8000]
        except Exception:
            pass
        low_title = title.lower()
        low_src = src.lower()
        if title == '429' or '429' in low_title or 'too many requests' in low_src:
            raise RuntimeError(f'Citilink: 429 (слишком частые запросы) url={url} title={title!r}')
        is_404 = '404' in title and 'не найден' in low_title
        is_403 = (
            '403' in title
            or 'доступ запрещ' in low_title
            or 'access denied' in low_title
            or 'forbidden' in low_title
        )
        if not (is_404 or is_403):
            return
        u = urlparse(url)
        looks_like_valid_path = '/catalog/' in (u.path or '')
        code = '403' if is_403 else '404'
        if looks_like_valid_path:
            raise RuntimeError(
                f'Citilink: страница {code} при валидном пути {u.path!r}. '
                f'Возможные причины: (а) slug категории устарел — обновите external_path '
                f'в CategoryListing; (б) Qrator anti-bot — проверьте headed-режим и профиль. '
                f'Аудит: `python manage.py citilink_validate_listings`. '
                f'url={url} title={title!r}'
            )
        raise RuntimeError(
            f'Citilink: {code}. Проверьте external_path в CategoryListing '
            f'(ожидается slug каталога, например "moduli-pamyati"). '
            f'url={url} title={title!r}'
        )

    def _warmup(self, driver: Any) -> None:
        if self._warmed_up:
            return
        try:
            self._driver_get(driver, f'{CITILINK_BASE}/')
            time.sleep(2.0 + random.uniform(0.8, 1.8))
            try:
                driver.execute_script('window.scrollBy(0, 400);')
            except Exception:
                pass
            time.sleep(0.8 + random.uniform(0, 0.6))
        except Exception:
            logger.debug('Citilink: warmup на главной не удался', exc_info=True)
        self._warmed_up = True

    def _scroll_listing(self, driver: Any) -> None:
        for _ in range(6):
            try:
                driver.execute_script('window.scrollBy(0, 900);')
            except Exception:
                break
            time.sleep(0.35)

    def _wait_cards(self, driver: Any) -> None:
        try:
            self._web_driver_wait(driver, self.catalog_element_wait).until(
                self._ec.any_of(
                    self._ec.presence_of_element_located(
                        (self._by.CSS_SELECTOR, '[data-meta-name="ProductHorizontalSnippet"]')
                    ),
                    self._ec.presence_of_element_located(
                        (self._by.CSS_SELECTOR, '[data-meta-name="ProductVerticalSnippet"]')
                    ),
                )
            )
        except Exception:
            try:
                title = driver.title
                cur = driver.current_url
            except Exception:
                title, cur = '', ''
            logger.error(
                'Citilink: нет карточек товаров за %ss: url=%s title=%r',
                self.catalog_element_wait, cur, title,
            )
            raise

    def _extract_rows(self, driver: Any) -> list[dict[str, Any]]:
        try:
            raw = driver.execute_script(_CITILINK_CARDS_EXTRACT_JS)
        except Exception:
            logger.warning('Citilink: batch JS не выполнился', exc_info=True)
            return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    @staticmethod
    def _row_to_parsed(row: dict[str, Any]) -> ParsedProduct | None:
        url = (row.get('url') or '').strip()
        name = (row.get('name') or '').strip()
        if not url or not name:
            return None
        variant_label, _ = extract_variant_from_url(url)
        if variant_label and variant_label not in name:
            name = f'{name} ({variant_label})'
        try:
            price = int(row.get('price'))
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        op = row.get('old_price')
        try:
            old_price: int | None = int(op) if op is not None else None
        except (TypeError, ValueError):
            old_price = None
        vc = (row.get('vendor_code') or '').strip() or _vendor_code_from_url(url)

        parsed_url = urlparse(url)
        config_param = parse_qs(parsed_url.query).get('config', [None])[0]
        if config_param:
            name = f"{name} [{config_param}]"

        return ParsedProduct(
            name=name,
            price=price,
            url=url,
            vendor_code=vc,
            image_url=str(row.get('image_url') or ''),
            old_price=old_price,
            is_available=bool(row.get('is_available', True)),
        )

    def _detect_redirect_to_root(self, driver: Any, expected_url: str) -> None:
        try:
            cur = driver.current_url or ''
        except Exception:
            return
        cur_path = (urlparse(cur).path or '/').rstrip('/') or '/'
        exp_path = (urlparse(expected_url).path or '/').rstrip('/') or '/'
        if cur_path in ('', '/') and exp_path not in ('', '/'):
            raise RuntimeError(
                f'Citilink: редирект на главную — каталога не существует. '
                f'Запрошено {expected_url}, получили {cur!r}. '
                f'Проверьте external_path в CategoryListing.'
            )

    def parse_category(self, category_url: str) -> list[ParsedProduct]:
        base = _normalize_catalog_url(category_url)
        if not base or CITILINK_HOST not in urlparse(base).netloc.lower():
            logger.error('Citilink: некорректный URL каталога: %r', category_url)
            return []

        logger.info('Парсинг категории Ситилинк: %s', base)

        for attempt in range(1, self.max_retries + 1):
            try:
                return self._do_parse_category(base)
            except Exception:
                logger.exception(
                    'Ошибка парсинга Citilink (попытка %d/%d): %s',
                    attempt, self.max_retries, base,
                )
                self.close()
                self._warmed_up = False
                if attempt < self.max_retries:
                    backoff = 2 ** attempt + random.uniform(0, 1)
                    logger.info('Повтор через %.1f сек.', backoff)
                    time.sleep(backoff)

        logger.error('Все попытки парсинга Citilink исчерпаны: %s', base)
        return []

    def _open_listing_page(self, driver: Any, base_url: str, page: int) -> None:
        page_url = _with_page_and_city(base_url, page, self._city_code)
        self._driver_get(driver, page_url)
        time.sleep((1.2 if page > 1 else 2.0) + random.uniform(0, 1.0))
        self._check_blocked(driver)
        if page == 1:
            self._detect_redirect_to_root(driver, base_url)

    def _detect_pages_count(self, driver: Any) -> int:
        try:
            pc = driver.execute_script(_PAGES_COUNT_JS)
        except Exception:
            return 1
        if isinstance(pc, (int, float)) and int(pc) > 0:
            return min(int(pc), self._max_pages)
        return 1

    def _do_parse_category(self, base_url: str) -> list[ParsedProduct]:
        driver = self._get_driver()
        self._warmup(driver)

        self._open_listing_page(driver, base_url, page=1)
        self._wait_cards(driver)
        self._scroll_listing(driver)

        pages = self._detect_pages_count(driver)
        all_rows: list[dict[str, Any]] = []
        first = self._extract_rows(driver)
        if not first:
            logger.warning('Citilink: на первой странице не удалось извлечь карточки')
        else:
            all_rows.extend(first)
            logger.info('Citilink: страница 1/%d, карточек на странице %d', pages, len(first))


        for page in range(2, pages + 1):
            self._random_delay()
            self._open_listing_page(driver, base_url, page)
            self._scroll_listing(driver)
            rows = self._extract_rows(driver)
            if not rows:
                logger.info('Citilink: страница %d пустая, остановка пагинации', page)
                break
            all_rows.extend(rows)
            logger.info('Citilink: страница %d/%d, карточек на странице %d', page, pages, len(rows))

        seen: dict[str, ParsedProduct] = {}
        for row in all_rows:
            parsed = self._row_to_parsed(row)
            if parsed and parsed.url not in seen:
                seen[parsed.url] = parsed
        products = list(seen.values())
        logger.info('Citilink: всего уникальных товаров: %d', len(products))
        return products
