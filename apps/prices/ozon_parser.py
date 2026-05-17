from __future__ import annotations

import logging
import os
import pickle
import random
import re
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.conf import settings

from .base_parser import BaseParser
from .ozon_composer import (
    OzonComposerSniffer,
    fetch_composer_in_browser,
    is_valid_ozon_product_name,
)
from .parsers import ChromeDriverMixin, ParsedProduct

logger = logging.getLogger(__name__)


_OZON_GRID_EXTRACT_JS = r"""
return (function () {
  if (!window.__ozonCatalog) window.__ozonCatalog = Object.create(null);
  var catalog = window.__ozonCatalog;
  var stats = {
    anchors_total: 0,
    skip_non_ozon: 0,
    skip_non_product_path: 0,
    skip_dup_url: 0,
    skip_bad_sku: 0,
    skip_bad_name: 0,
    skip_no_price: 0,
    skip_js_error: 0,
    accepted: 0
  };
  function digitsFromPriceText(t) {
    if (!t) return null;
    var s = String(t).replace(/\s+/g, ' ');
    var m = s.match(/([\d\u00a0\s]{2,})\s*[₽\u20bd]/);
    if (m) {
      var d = m[1].replace(/[^\d]/g, '');
      if (/^\d{2,}$/.test(d)) return parseInt(d, 10);
    }
    m = s.match(/(?:от|цена)\s*([\d\u00a0\s]{3,})/i);
    if (m) {
      var d2 = m[1].replace(/[^\d]/g, '');
      if (/^\d{3,}$/.test(d2)) return parseInt(d2, 10);
    }
    return null;
  }
  function plausiblePrice(n) {
    return n >= 299 && n <= 9999999;
  }
  function largestPlausiblePrice(txt) {
    if (!txt) return null;
    var re = /(\d[\d\u00a0\s]{2,}\d|\d{4,})/g;
    var m, best = null;
    while ((m = re.exec(txt)) !== null) {
      var d = parseInt(String(m[1]).replace(/[^\d]/g, ''), 10);
      if (plausiblePrice(d)) best = d;
    }
    return best;
  }
  function extractPrice(anchor, cardRoot) {
    var roots = [];
    if (cardRoot) roots.push(cardRoot);
    roots.push(anchor);
    for (var ri = 0; ri < roots.length; ri++) {
      var root = roots[ri];
      if (!root) continue;
      var priceEls = root.querySelectorAll(
        '[data-widget*="price"],[data-widget*="Price"],[data-widget*="webPrice"],span[class*="price"],span[class*="Price"],div[class*="price"]'
      );
      for (var pi = 0; pi < priceEls.length && pi < 12; pi++) {
        var p = digitsFromPriceText(priceEls[pi].textContent || '');
        if (p) return p;
        var fb = largestPlausiblePrice(priceEls[pi].textContent || '');
        if (fb) return fb;
      }
      var el = root;
      for (var up = 0; up < 16 && el; up++) {
        var txt = el.innerText || '';
        var p2 = digitsFromPriceText(txt);
        if (p2) return p2;
        var fb2 = largestPlausiblePrice(txt);
        if (fb2) return fb2;
        el = el.parentElement;
      }
    }
    return null;
  }
  function skuFromPath(pathUrl) {
    var m = String(pathUrl || '').match(/-(\d{5,})\/?$/);
    if (m) return m[1];
    m = String(pathUrl || '').match(/\/product\/(\d{5,})\/?$/);
    if (m) return m[1];
    m = String(pathUrl || '').match(/\/(\d{7,12})\/?$/);
    return m ? m[1] : '';
  }
  function firstSrcFromSet(raw) {
    if (!raw) return '';
    var parts = String(raw).split(',');
    for (var i = 0; i < parts.length; i++) {
      var token = parts[i].trim().split(/\s+/)[0];
      if (token) return token;
    }
    return '';
  }
  function normalizeImgUrl(raw) {
    var s = (raw || '').trim();
    if (!s) return '';
    if (s.indexOf('data:') === 0 || s.indexOf('blob:') === 0) return '';
    if (s.indexOf('//') === 0) return 'https:' + s;
    if (s.indexOf('/') === 0) return 'https://www.ozon.ru' + s;
    return s;
  }
  function pickImg(root) {
    if (!root) return '';
    var picSrc = root.querySelector('picture source[srcset],picture source[data-srcset]');
    if (picSrc) {
      var u = normalizeImgUrl(
        firstSrcFromSet(picSrc.getAttribute('srcset') || picSrc.getAttribute('data-srcset') || '')
      );
      if (u) return u;
    }
    var im = root.querySelector('img[src],img[data-src],img[srcset],img[data-srcset]');
    if (im) {
      var u2 = normalizeImgUrl(im.getAttribute('src') || im.getAttribute('data-src') || '');
      if (u2) return u2;
      var u3 = normalizeImgUrl(
        firstSrcFromSet(im.getAttribute('srcset') || im.getAttribute('data-srcset') || '')
      );
      if (u3) return u3;
    }
    return '';
  }
  function normalizeName(raw) {
    var s = String(raw || '').replace(/[\u00a0\u2009\u202f]/g, ' ').replace(/\s+/g, ' ').trim();
    if (!s) return '';
    var low = s.toLowerCase();
    var bad = {
      'распродажа': 1,
      'sale': 1,
      'скидки': 1,
      'скидка': 1,
      'акция': 1,
      'хит': 1,
      'топ': 1,
      'новинка': 1,
      'купить': 1,
      'в корзину': 1,
      'в избранное': 1,
      'цена что надо': 1,
      'суперцена': 1
    };
    if (bad[low]) return '';
    if (/(балл\w*\s+за\s+отзыв|за\s+отзыв|к[эе]шб[еэ]к|кэшбек|кешбек)/i.test(low)) return '';
    if (/^\+?\s*\d+\s*морков(ка|ки|ок)?$/i.test(low)) return '';
    if (/морков(ка|ки|ок)/i.test(low) && low.length <= 24) return '';
    if (s.length < 6) return '';
    return s;
  }
  function slugNameFromUrl(pathUrl) {
    try {
      var m = String(pathUrl || '').match(/\/product\/([^\/]+)-\d+\/?$/);
      if (!m) {
        m = String(pathUrl || '').match(/\/product\/([^\/]+)\/?$/);
      }
      if (!m) return '';
      var raw = decodeURIComponent(m[1] || '').replace(/-/g, ' ').trim();
      if (raw.length < 4) return '';
      var low = raw.toLowerCase();
      if (low === 'product' || low === 'ozon') return '';
      return raw;
    } catch (e) {
      return '';
    }
  }
  function isTooGenericName(name, fromSlug) {
    var low = String(name || '').toLowerCase().trim();
    if (!low) return true;
    var generic = {
      'ноутбуки': 1,
      'смартфоны': 1,
      'планшеты': 1,
      'мониторы': 1,
      'товары': 1,
      'каталог': 1
    };
    if (generic[low]) return true;
    if (!fromSlug && /^[a-zа-яё]+$/i.test(low) && low.length <= 12) return true;
    return false;
  }
  function findCardRoot(a) {
    if (a.closest) {
      var c = a.closest('[data-index], [class*="tile"], [class*="Tile"], article, div[data-widget]');
      if (c) return c;
    }
    var cardRoot = a;
    for (var upRoot = 0; upRoot < 10 && cardRoot; upRoot++) {
      cardRoot = cardRoot.parentElement;
    }
    return cardRoot;
  }
  function extractName(a, root) {
    var cands = [];
    cands.push(a.getAttribute('title') || '');
    cands.push(a.getAttribute('aria-label') || '');
    cands.push((a.innerText || '').split('\n')[0] || '');
    if (root) {
      var ns = root.querySelectorAll(
        '[data-widget*="title"], [data-widget*="name"], h1, h2, h3, [title], [aria-label]'
      );
      for (var i = 0; i < ns.length && i < 20; i++) {
        var n = ns[i];
        cands.push(n.getAttribute('title') || '');
        cands.push(n.getAttribute('aria-label') || '');
        cands.push(n.textContent || '');
      }
    }
    for (var j = 0; j < cands.length; j++) {
      var nn = normalizeName(cands[j]);
      if (nn) return nn;
    }
    return '';
  }
  function collectAnchors() {
    var out = [];
    var seenA = Object.create(null);
    function pushAnchor(a) {
      if (!a || !a.href) return;
      var k = a.href.split('?')[0];
      if (seenA[k]) return;
      seenA[k] = true;
      out.push(a);
    }
    var pag = document.getElementById('contentScrollPaginator');
    if (pag) {
      var tiles = pag.querySelectorAll('[class*="tile-root"]');
      for (var ti = 0; ti < tiles.length; ti++) {
        var link = tiles[ti].querySelector(
          'a[data-prerender="true"], a[href*="/product/"]'
        );
        if (link) pushAnchor(link);
      }
    }
    if (out.length === 0) {
      var all = document.querySelectorAll('a[href*="/product/"]');
      for (var ai = 0; ai < all.length; ai++) pushAnchor(all[ai]);
    }
    return out;
  }
  var anchors = collectAnchors();
  var seen = Object.create(null);
  var out = [];
  stats.anchors_total = anchors.length;
  for (var i = 0; i < anchors.length; i++) {
    var a = anchors[i];
    try {
      var href = a.href || '';
      if (!href || href.indexOf('ozon.ru') === -1) { stats.skip_non_ozon++; continue; }
      var u = new URL(href);
      if (u.pathname.indexOf('/product/') === -1) { stats.skip_non_product_path++; continue; }
      var pathUrl = u.origin + u.pathname;
      if (seen[pathUrl]) { stats.skip_dup_url++; continue; }
      var sku = skuFromPath(pathUrl);
      if (!sku) { stats.skip_bad_sku++; continue; }
      var cardRoot = findCardRoot(a);
      var bySlug = slugNameFromUrl(pathUrl);
      var name = extractName(a, cardRoot);
      var fromSlug = false;
      if (!name || isTooGenericName(name, false)) {
        if (bySlug) { name = bySlug; fromSlug = true; }
      }
      if (!name || isTooGenericName(name, fromSlug)) { stats.skip_bad_name++; continue; }
      var price = extractPrice(a, cardRoot);
      if (!price) { stats.skip_no_price++; }
      var img = '';
      var isAvail = true;
      try {
        var root = cardRoot || a;
        for (var j = 0; j < 10 && root; j++) {
          img = pickImg(root);
          if (img) break;
          root = root.parentElement;
          if (!root) break;
        }
        var block = a;
        for (var up2 = 0; up2 < 14 && block; up2++) {
          block = block.parentElement;
          if (!block) break;
          var low = (block.innerText || '').toLowerCase();
          if (low.indexOf('нет в наличии') !== -1) { isAvail = false; break; }
          if (low.indexOf('нет в продаже') !== -1) { isAvail = false; break; }
          if (low.indexOf('закончился') !== -1) { isAvail = false; break; }
          if (low.indexOf('уведомить о поступлении') !== -1) { isAvail = false; break; }
        }
      } catch (e2) {}
      var row = {
        name: name,
        url: pathUrl,
        price: price,
        old_price: null,
        image_url: img,
        vendor_code: sku,
        is_available: isAvail
      };
      if (!catalog[pathUrl]) {
        catalog[pathUrl] = row;
        stats.accepted++;
      } else {
        catalog[pathUrl] = row;
      }
      seen[pathUrl] = true;
    } catch (e) { stats.skip_js_error++; }
  }
  var out = [];
  for (var key in catalog) {
    if (catalog.hasOwnProperty(key)) out.push(catalog[key]);
  }
  return { rows: out, stats: stats, catalog_size: out.length };
})();
"""


_BLOCK_URL_MARKERS = ('/captcha', '/blocked', '/challenge', '/antibot')
_BLOCK_TEXT_MARKERS = (
    'access denied',
    'forbidden',
    'your request looks automated',
    'too many requests',
    'temporarily unavailable',
    'доступ ограничен',
    'подтвердите, что вы не робот',
)


class OzonBlockedError(RuntimeError):
    pass


def _normalize_ozon_category_url(raw: str) -> str:
    s = (raw or '').strip()
    if not s:
        return ''
    if not s.startswith('http'):
        s = 'https://www.ozon.ru/' + s.lstrip('/')
    u = urlparse(s)
    if 'ozon.ru' not in (u.netloc or '').lower():
        return ''
    return urlunparse((u.scheme or 'https', 'www.ozon.ru', u.path or '/', '', '', ''))


def _sku_from_url(url: str) -> str:
    for pattern in (
        r'-(\d{5,})(?:/|\?|$)',
        r'/product/(\d{5,})(?:/|\?|$)',
        r'/(\d{7,12})(?:/|\?|$)',
    ):
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return ''


class OzonParser(ChromeDriverMixin, BaseParser):

    OZON_BASE = 'https://www.ozon.ru'

    def __init__(self) -> None:
        self._init_chrome_runtime(
            page_timeout_setting='OZON_PAGE_LOAD_TIMEOUT',
            page_timeout_default=getattr(settings, 'DNS_PAGE_LOAD_TIMEOUT', 120),
            headless_setting='OZON_HEADLESS',
            headless_default=False,
            user_data_dir_setting='OZON_USER_DATA_DIR',
        )
        self._scroll_max_rounds = int(getattr(settings, 'OZON_SCROLL_MAX_ROUNDS', 50))
        self._scroll_min_rounds = int(getattr(settings, 'OZON_SCROLL_MIN_ROUNDS', 15))
        self._scroll_stability_threshold = int(getattr(settings, 'OZON_SCROLL_STABILITY_THRESHOLD', 8))
        self._scroll_pause = (
            float(getattr(settings, 'OZON_SCROLL_PAUSE_MIN', 1.2)),
            float(getattr(settings, 'OZON_SCROLL_PAUSE_MAX', 2.8)),
        )
        self._cookie_file = (getattr(settings, 'OZON_COOKIE_FILE', '') or '').strip() or None
        self._pagination_max_pages = int(getattr(settings, 'OZON_PAGINATION_MAX_PAGES', 8))
        self._composer_enabled = bool(getattr(settings, 'OZON_COMPOSER_ENABLED', True))
        self._warmed_up = False
        self._composer_sniffer: OzonComposerSniffer | None = None

    def _build_options(self) -> Any:
        options = super()._build_options()
        try:
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        except Exception:
            pass
        return options

    def _get_driver(self) -> Any:
        if self._driver is None:
            self._driver = self._build_driver()
            if self._composer_enabled:
                self._composer_sniffer = OzonComposerSniffer(self._driver)
                self._composer_sniffer.enable()
        return self._driver

    def close(self) -> None:
        self._composer_sniffer = None
        super().close()

    def _check_block(self, driver: Any) -> tuple[bool, str]:
        try:
            cur_url = (driver.current_url or '').lower()
        except Exception:
            cur_url = ''
        for marker in _BLOCK_URL_MARKERS:
            if marker in cur_url:
                return True, f'block_url:{marker}'

        try:
            low = (driver.page_source or '').lower()
        except Exception:
            return True, 'no_page_source'

        for marker in _BLOCK_TEXT_MARKERS:
            if marker in low:
                return True, f'block_text:{marker}'
        if 'recaptcha' in low and 'iframe' in low:
            return True, 'recaptcha'
        if 'captcha' in low or 'подтвердите что вы не робот' in low:
            return True, 'captcha_text'
        return False, 'OK'

    def _raise_if_blocked(self, driver: Any) -> None:
        blocked, reason = self._check_block(driver)
        if blocked:
            raise OzonBlockedError(reason)

    def _log_page_diagnostics(self, driver: Any, label: str) -> None:
        try:
            cur_url = driver.current_url or ''
        except Exception:
            cur_url = ''
        try:
            title = driver.title or ''
        except Exception:
            title = ''
        try:
            body_len = int(driver.execute_script(
                'return (document.body && document.body.innerHTML) ? document.body.innerHTML.length : 0;'
            ))
        except Exception:
            body_len = -1
        try:
            counts = driver.execute_script(
                'return {'
                '  a: document.querySelectorAll("a").length,'
                '  ozon: document.querySelectorAll("a[href*=\\"ozon.ru\\"]").length,'
                '  product: document.querySelectorAll("a[href*=\\"/product/\\"]").length,'
                '  category: document.querySelectorAll("a[href*=\\"/category/\\"]").length'
                '};'
            ) or {}
        except Exception:
            counts = {}
        logger.info(
            'Ozon[%s]: url=%s title=%r body=%dB anchors=%s',
            label, cur_url, title, body_len, counts,
        )

    def _wait_for_products(self, driver: Any, timeout: float = 15.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                n = int(driver.execute_script(
                    'return document.querySelectorAll(\'a[href*="/product/"]\').length;'
                ))
            except Exception:
                n = 0
            if n > 0:
                return True
            time.sleep(0.5)
        return False

    def _dump_page_for_debug(self, driver: Any, reason: str) -> None:
        try:
            src = driver.page_source or ''
        except Exception:
            src = ''
        head = src[:2000].replace('\n', ' ')
        logger.warning('Ozon: пусто (%s). Первые 2KB HTML: %s', reason, head)

    def _warmup(self, driver: Any) -> None:
        if self._warmed_up:
            return
        try:
            self._driver_get(driver, f'{self.OZON_BASE}/')
            time.sleep(2.0 + random.uniform(0.8, 1.8))
            self._apply_saved_cookies(driver)
            try:
                driver.execute_script('window.scrollBy(0, 600);')
            except Exception:
                pass
            time.sleep(0.8 + random.uniform(0, 0.6))
        except Exception:
            logger.debug('Ozon: warmup на главной не удался', exc_info=True)
        self._warmed_up = True

    def _apply_saved_cookies(self, driver: Any) -> None:
        if not self._cookie_file or not os.path.isfile(self._cookie_file):
            return
        try:
            with open(self._cookie_file, 'rb') as f:
                cookies = pickle.load(f)
            for c in cookies:
                try:
                    driver.add_cookie(c)
                except Exception:
                    continue
            driver.refresh()
            time.sleep(random.uniform(1.0, 1.8))
            logger.info('Ozon: загружены cookies из %s', self._cookie_file)
        except Exception:
            logger.debug('Ozon: не удалось загрузить cookies', exc_info=True)

    def _save_cookies(self, driver: Any) -> None:
        if not self._cookie_file:
            return
        try:
            cookies = driver.get_cookies()
            d = os.path.dirname(os.path.abspath(self._cookie_file))
            if d:
                os.makedirs(d, exist_ok=True)
            with open(self._cookie_file, 'wb') as f:
                pickle.dump(cookies, f)
        except Exception:
            logger.debug('Ozon: не удалось сохранить cookies', exc_info=True)

    _SCROLL_TICK_JS = r"""
return (function () {
  var anchors = document.querySelectorAll('a[href*="/product/"]');
  var last = anchors.length ? anchors[anchors.length - 1] : null;
  if (last) {
    try { last.scrollIntoView({block: 'end', inline: 'nearest', behavior: 'auto'}); } catch (e) {}
  }
  var step = Math.max(400, Math.floor(window.innerHeight * 0.85));
  window.scrollBy(0, step);
  var doc = document.scrollingElement || document.documentElement || document.body;
  var h = Math.max(
    document.body ? document.body.scrollHeight : 0,
    document.documentElement ? document.documentElement.scrollHeight : 0
  );
  window.scrollTo(0, h);
  if (doc) doc.scrollTop = h;
  try {
    window.dispatchEvent(new Event('scroll'));
  } catch (e) {}
  return anchors.length;
})();
"""

    _RESET_CATALOG_JS = 'window.__ozonCatalog = Object.create(null); return true;'

    def _human_scroll_tick(self, driver: Any) -> int:
        try:
            n = driver.execute_script(self._SCROLL_TICK_JS)
        except Exception:
            n = 0
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 0
        time.sleep(random.uniform(*self._scroll_pause))
        return n

    def _extract_grid(
        self, driver: Any
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        try:
            raw = driver.execute_script(_OZON_GRID_EXTRACT_JS)
        except Exception:
            logger.debug('Ozon: JS-извлечение не удалось', exc_info=True)
            return [], {}
        if not isinstance(raw, dict):
            return [], {}
        rows_obj = raw.get('rows')
        rows = [r for r in rows_obj if isinstance(r, dict)] if isinstance(rows_obj, list) else []
        stats_obj = raw.get('stats') or {}
        stats: dict[str, int] = {}
        if isinstance(stats_obj, dict):
            for k, v in stats_obj.items():
                try:
                    stats[str(k)] = int(v)
                except (TypeError, ValueError):
                    continue
        return rows, stats

    @staticmethod
    def _merge_rows(acc: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> None:
        for row in rows:
            OzonParser._merge_row(acc, row)

    @staticmethod
    def _merge_row(acc: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
        url = (row.get('url') or '').strip()
        if not url:
            return
        prev = acc.get(url)
        if not prev:
            acc[url] = row
            return
        for key in ('name', 'price', 'old_price', 'image_url', 'vendor_code', 'is_available', 'source'):
            new_val = row.get(key)
            if new_val is None or new_val == '':
                continue
            if key == 'price':
                try:
                    if int(new_val) > 0:
                        if not prev.get('price'):
                            prev[key] = new_val
                except (TypeError, ValueError):
                    pass
            elif not prev.get(key):
                prev[key] = new_val

    def _collect_composer_rows(self, driver: Any, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self._composer_enabled:
            return rows
        if self._composer_sniffer is not None:
            rows.extend(self._composer_sniffer.drain())
        if len(rows) < 5:
            rows.extend(fetch_composer_in_browser(driver, page_url))
        deduped: dict[str, dict[str, Any]] = {}
        self._merge_rows(deduped, rows)
        return list(deduped.values())

    def parse_category(self, category_url: str) -> list[ParsedProduct]:
        base = _normalize_ozon_category_url(category_url)
        if not base:
            logger.error('Ozon: пустой или некорректный URL категории: %r', category_url)
            return []

        logger.info('Парсинг категории Ozon: %s', base)
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._do_parse_category(base)
            except OzonBlockedError:
                raise
            except Exception:
                logger.exception(
                    'Ошибка парсинга Ozon (попытка %d/%d): %s',
                    attempt, self.max_retries, base,
                )
                self.close()
                self._warmed_up = False
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt + random.uniform(0, 1.5))
        logger.error('Все попытки парсинга Ozon исчерпаны: %s', base)
        return []

    @staticmethod
    def _with_page_param(base_url: str, page: int) -> str:
        u = urlparse(base_url)
        q = parse_qs(u.query, keep_blank_values=True)
        q['page'] = [str(max(1, int(page)))]
        return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q, doseq=True), u.fragment))

    def _parse_listing_page(self, driver: Any, page_url: str, *, reset_catalog: bool) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
        if reset_catalog:
            try:
                driver.execute_script(self._RESET_CATALOG_JS)
            except Exception:
                pass
            if self._composer_sniffer is not None:
                self._composer_sniffer.reset_seen()
        self._driver_get(driver, page_url)
        time.sleep(2.0 + random.uniform(0, 1.5))
        self._raise_if_blocked(driver)
        if not self._wait_for_products(driver, timeout=20.0):
            self._raise_if_blocked(driver)
        time.sleep(1.5 + random.uniform(0.5, 1.0))

        merged: dict[str, dict[str, Any]] = {}
        stats_total: dict[str, int] = {'composer_rows': 0, 'dom_rows': 0}
        prev_catalog_size = 0
        stable = 0

        composer_boot = self._collect_composer_rows(driver, page_url)
        self._merge_rows(merged, composer_boot)
        stats_total['composer_rows'] = len(composer_boot)
        if composer_boot:
            logger.info('Ozon: composer после загрузки — %d товаров', len(composer_boot))

        for rnd in range(self._scroll_max_rounds):
            self._raise_if_blocked(driver)
            composer_rows = self._collect_composer_rows(driver, page_url)
            if composer_rows:
                before = len(merged)
                self._merge_rows(merged, composer_rows)
                stats_total['composer_rows'] = stats_total.get('composer_rows', 0) + len(composer_rows)
                if len(merged) > before:
                    stable = 0

            rows, stats = self._extract_grid(driver)
            priced_dom = [r for r in rows if r.get('price')]
            stats_total['dom_rows'] = stats_total.get('dom_rows', 0) + len(priced_dom)
            self._merge_rows(merged, rows)
            for k, v in stats.items():
                stats_total[k] = stats_total.get(k, 0) + v

            anchors = int(stats.get('anchors_total') or 0)
            accepted_dom = int(stats.get('accepted') or 0)
            if anchors > 5 and accepted_dom == 0 and not composer_rows:
                logger.warning(
                    'Ozon: %d якорей, 0 DOM/composer в раунде %d. stats=%s',
                    anchors, rnd + 1, stats,
                )

            catalog_size = len(merged)
            delta = catalog_size - prev_catalog_size
            if delta > 0:
                stable = 0
            else:
                stable += 1
                if stable >= self._scroll_stability_threshold and (rnd + 1) >= self._scroll_min_rounds:
                    logger.info(
                        'Ozon: каталог стабилизировался, раундов %d, уникальных %d',
                        rnd + 1, catalog_size,
                    )
                    break
            prev_catalog_size = catalog_size
            self._human_scroll_tick(driver)

        return merged, stats_total

    def _do_parse_category(self, listing_url: str) -> list[ParsedProduct]:
        driver = self._get_driver()
        self._warmup(driver)

        merged, stats_total = self._parse_listing_page(
            driver, listing_url, reset_catalog=True,
        )
        self._log_page_diagnostics(driver, 'after_page_1')

        if len(merged) < 40 and self._pagination_max_pages > 1:
            prev_count = len(merged)
            for page in range(2, self._pagination_max_pages + 1):
                page_url = self._with_page_param(listing_url, page)
                page_merged, page_stats = self._parse_listing_page(
                    driver, page_url, reset_catalog=False,
                )
                for k, v in page_stats.items():
                    stats_total[k] = stats_total.get(k, 0) + v
                before = len(merged)
                self._merge_rows(merged, list(page_merged.values()))
                gained = len(merged) - before
                logger.info(
                    'Ozon: страница %d — добавлено %d новых (всего %d)',
                    page, gained, len(merged),
                )
                if gained == 0 and len(page_merged) <= prev_count:
                    break
                prev_count = len(merged)

        with_price = sum(1 for r in merged.values() if r.get('price'))
        products = self._rows_to_parsed(list(merged.values()))
        if stats_total:
            logger.info('Ozon: extract stats total: %s', stats_total)
        logger.info(
            'Ozon: уникальных URL %d, с ценой %d, в ParsedProduct %d',
            len(merged), with_price, len(products),
        )
        self._save_cookies(driver)
        return products

    @staticmethod
    def _rows_to_parsed(rows: list[dict[str, Any]]) -> list[ParsedProduct]:
        out: list[ParsedProduct] = []
        for row in rows:
            url = (row.get('url') or '').strip()
            name = (row.get('name') or '').strip()
            if not url or not name or not is_valid_ozon_product_name(name):
                continue
            try:
                price = int(row['price'])
            except (TypeError, ValueError, KeyError):
                continue
            if price <= 0:
                continue
            op = row.get('old_price')
            try:
                old = int(op) if op is not None else None
            except (TypeError, ValueError):
                old = None
            vc = (row.get('vendor_code') or '').strip() or _sku_from_url(url)
            out.append(
                ParsedProduct(
                    name=name[:500],
                    price=price,
                    url=url,
                    vendor_code=vc,
                    image_url=str(row.get('image_url') or '')[:1024],
                    old_price=old,
                    is_available=bool(row.get('is_available', True)),
                )
            )
        return out
