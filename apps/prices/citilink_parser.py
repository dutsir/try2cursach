
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
    // Сначала структурированные сигналы — надёжнее текста.
    var av = card.getAttribute('data-meta-availability')
      || (card.querySelector('[data-meta-availability]')
          ? card.querySelector('[data-meta-availability]').getAttribute('data-meta-availability')
          : '');
    if (av) {
      var a = String(av).toLowerCase();
      if (a === 'false' || a === '0' || a === 'outofstock' || a === 'out_of_stock') return false;
      if (a === 'true' || a === '1' || a === 'instock' || a === 'in_stock') return true;
    }
    if (card.querySelector('[data-meta-name="SubscribeToBackInStockButton"],'
      + '[data-meta-name="OutOfStockBlock"],'
      + '[data-meta-name*="OutOfStock"]')) {
      return false;
    }
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
  // Несколько вариантов селекторов карточек: Citilink периодически
  // меняет data-meta-name (SearchSnippet, Snippet*, *Layout), а на
  // мобильной вёрстке встречаются собственные варианты.
  var cards = document.querySelectorAll(
    '[data-meta-name="ProductHorizontalSnippet"],'
    + '[data-meta-name="ProductVerticalSnippet"],'
    + '[data-meta-name="ProductCardVerticalLayout"],'
    + '[data-meta-name="ProductCardHorizontalLayout"],'
    + '[data-meta-name="SearchSnippet"],'
    + '[data-meta-name="ProductSnippet"]'
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
    if (seen[href]) continue;
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


# Fallback-извлечение из __NEXT_DATA__: Citilink — Next.js, и при поломке
# data-meta-* селекторов структурированные данные всё равно остаются в JSON
# в <script id="__NEXT_DATA__">. Рекурсивно ищем объекты, похожие на продукты:
# у них есть name/title, price, и url/path/slug ведущий на /product/.
_CITILINK_NEXTDATA_EXTRACT_JS = r"""
return (function () {
  var script = document.getElementById('__NEXT_DATA__');
  if (!script) return null;
  var raw = script.textContent || script.innerText || '';
  if (!raw) return null;
  var data;
  try { data = JSON.parse(raw); } catch (e) { return null; }

  function cleanInt(v) {
    if (v == null) return null;
    if (typeof v === 'number' && isFinite(v)) return Math.round(v);
    var s = String(v).replace(/\s+/g, '').replace(/[^\d]/g, '');
    return /^\d+$/.test(s) ? parseInt(s, 10) : null;
  }
  function normalizeUrl(u) {
    if (!u) return '';
    var s = String(u).trim();
    if (!s) return '';
    if (s.indexOf('http') === 0) return s;
    if (s.indexOf('//') === 0) return 'https:' + s;
    return 'https://www.citilink.ru' + (s.charAt(0) === '/' ? s : '/' + s);
  }
  function pickName(o) {
    return (o.name || o.title || o.shortName || o.fullName || '').toString().trim();
  }
  function pickUrl(o) {
    var u = o.url || o.link || o.href || o.path || '';
    if (!u && o.slug) {
      u = '/product/' + String(o.slug).replace(/^\/+/, '');
    }
    return normalizeUrl(u);
  }
  function pickPrice(o) {
    if (o.price && typeof o.price === 'object') {
      return cleanInt(o.price.current || o.price.value || o.price.amount || o.price.client);
    }
    return cleanInt(o.price || o.priceCurrent || o.currentPrice || o.clientPrice);
  }
  function pickOldPrice(o) {
    if (o.price && typeof o.price === 'object') {
      return cleanInt(o.price.old || o.price.prev || o.price.previous);
    }
    return cleanInt(o.oldPrice || o.previousPrice || o.priceOld);
  }
  function pickImage(o) {
    var img = o.image || o.imageUrl || o.preview || o.imagePreview || '';
    if (img && typeof img === 'object') {
      img = img.url || img.src || img.default || img.large || '';
    }
    if (!img && Array.isArray(o.images) && o.images.length) {
      var first = o.images[0];
      if (typeof first === 'string') img = first;
      else if (first && typeof first === 'object') img = first.url || first.src || '';
    }
    return normalizeUrl(img);
  }
  function isProductLike(o) {
    if (!o || typeof o !== 'object') return false;
    var url = pickUrl(o);
    if (!url || url.indexOf('/product/') === -1) return false;
    if (!pickName(o)) return false;
    if (pickPrice(o) == null) return false;
    return true;
  }

  var out = [];
  var seen = Object.create(null);
  var stack = [data];
  var guard = 0;
  while (stack.length && guard < 200000) {
    guard++;
    var node = stack.pop();
    if (!node) continue;
    if (Array.isArray(node)) {
      for (var i = 0; i < node.length; i++) stack.push(node[i]);
      continue;
    }
    if (typeof node !== 'object') continue;
    if (isProductLike(node)) {
      var url = pickUrl(node);
      if (!seen[url]) {
        seen[url] = true;
        var price = pickPrice(node);
        var av = node.availability || node.available || node.inStock;
        var isAvail = true;
        if (typeof av === 'boolean') isAvail = av;
        else if (typeof av === 'string') {
          var a = av.toLowerCase();
          if (a === 'false' || a === 'outofstock' || a === 'out_of_stock' || a === '0') isAvail = false;
        }
        out.push({
          name: pickName(node),
          url: url,
          price: price,
          old_price: pickOldPrice(node),
          image_url: pickImage(node),
          vendor_code: String(node.id || node.offerId || node.productId || node.sku || ''),
          is_available: isAvail
        });
      }
    }
    for (var k in node) {
      if (Object.prototype.hasOwnProperty.call(node, k)) {
        var v = node[k];
        if (v && typeof v === 'object') stack.push(v);
      }
    }
  }
  return out;
})();
"""

_PAGES_COUNT_JS = r"""
return (function () {
  var PAGE_SIZE = 48;
  // 1) Несколько вариантов data-атрибута со счётчиком товаров на странице.
  var countSelectors = [
    '[data-meta-name="SubcategoryPageTitle__product-count"]',
    '[data-meta-product-count]',
    '[data-meta-name*="ProductCount"]',
  ];
  for (var i = 0; i < countSelectors.length; i++) {
    var el = document.querySelector(countSelectors[i]);
    if (!el) continue;
    var raw = el.getAttribute('data-meta-product-count') || el.textContent || '';
    var nums = String(raw).match(/\d+/);
    var n = nums ? parseInt(nums[0], 10) : 0;
    if (n && n > 0) return Math.max(1, Math.ceil(n / PAGE_SIZE));
  }
  // 2) Самая большая ссылка-цифра в блоке пагинации.
  var pgLinks = document.querySelectorAll(
    '[data-meta-name="PaginationButton"], a[href*="p="], button[data-meta-name*="Pagination"]'
  );
  var maxPage = 0;
  for (var j = 0; j < pgLinks.length; j++) {
    var lnk = pgLinks[j];
    var txt = (lnk.innerText || lnk.textContent || '').trim();
    var m = txt.match(/^\d+$/);
    if (m) {
      var p = parseInt(m[0], 10);
      if (p > maxPage) maxPage = p;
    }
    var href = lnk.getAttribute && lnk.getAttribute('href');
    if (href) {
      var hm = href.match(/[?&]p=(\d+)/);
      if (hm) {
        var hp = parseInt(hm[1], 10);
        if (hp > maxPage) maxPage = hp;
      }
    }
  }
  if (maxPage > 0) return maxPage;
  // 3) __NEXT_DATA__ как последний шанс.
  var script = document.getElementById('__NEXT_DATA__');
  if (script) {
    try {
      var data = JSON.parse(script.textContent || '');
      var stack = [data];
      var guard = 0;
      while (stack.length && guard < 50000) {
        guard++;
        var node = stack.pop();
        if (!node || typeof node !== 'object') continue;
        if (Array.isArray(node)) {
          for (var k = 0; k < node.length; k++) stack.push(node[k]);
          continue;
        }
        var total = node.totalCount || node.total || node.productsCount;
        if (typeof total === 'number' && total > 0) {
          return Math.max(1, Math.ceil(total / PAGE_SIZE));
        }
        var pages = node.pagesCount || node.totalPages;
        if (typeof pages === 'number' && pages > 0) return pages;
        for (var p2 in node) {
          if (Object.prototype.hasOwnProperty.call(node, p2)) {
            var v = node[p2];
            if (v && typeof v === 'object') stack.push(v);
          }
        }
      }
    } catch (e) {}
  }
  return 1;
})();
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

    _CARD_PRESENCE_SELECTOR = (
        '[data-meta-name="ProductHorizontalSnippet"],'
        '[data-meta-name="ProductVerticalSnippet"],'
        '[data-meta-name="ProductCardVerticalLayout"],'
        '[data-meta-name="ProductCardHorizontalLayout"],'
        '[data-meta-name="SearchSnippet"],'
        '[data-meta-name="ProductSnippet"]'
    )

    def _wait_cards(self, driver: Any) -> None:
        try:
            self._web_driver_wait(driver, self.catalog_element_wait).until(
                self._ec.presence_of_element_located(
                    (self._by.CSS_SELECTOR, self._CARD_PRESENCE_SELECTOR)
                )
            )
        except Exception:
            # DOM-карточки не пришли — но __NEXT_DATA__ может содержать товары
            # (страница загружается без клиентской гидратации). Дадим fallback-у
            # шанс вместо немедленного падения.
            try:
                has_nd = bool(driver.execute_script(
                    'return !!document.getElementById("__NEXT_DATA__");'
                ))
            except Exception:
                has_nd = False
            if has_nd:
                logger.warning(
                    'Citilink: DOM-карточки за %ss не появились, '
                    'но __NEXT_DATA__ есть — продолжаем через fallback.',
                    self.catalog_element_wait,
                )
                return
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
        rows: list[dict[str, Any]] = []
        try:
            raw = driver.execute_script(_CITILINK_CARDS_EXTRACT_JS)
            if isinstance(raw, list):
                rows = [item for item in raw if isinstance(item, dict)]
        except Exception:
            logger.warning('Citilink: batch JS не выполнился', exc_info=True)

        if rows:
            return rows

        # Fallback: data-meta-* селекторы не дали карточек.
        # Пробуем достать товары из __NEXT_DATA__ — Citilink-SSR оставляет
        # структурированные данные продуктов в JSON, который не зависит от
        # текущей разметки и переживает редизайн.
        try:
            raw_nd = driver.execute_script(_CITILINK_NEXTDATA_EXTRACT_JS)
            if isinstance(raw_nd, list):
                nd_rows = [item for item in raw_nd if isinstance(item, dict)]
                if nd_rows:
                    logger.info(
                        'Citilink: DOM-карточек 0, восстановлено из __NEXT_DATA__: %d',
                        len(nd_rows),
                    )
                    return nd_rows
        except Exception:
            logger.warning('Citilink: __NEXT_DATA__ fallback не выполнился', exc_info=True)
        return []

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
