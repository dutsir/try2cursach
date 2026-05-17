from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_COMPOSER_URL_MARKERS = (
    'entrypoint-api.bx/page/json',
    'composer-api.bx/page/json',
)

_CATALOG_COMPONENT_HINTS = (
    'searchresults',
    'tilegrid',
    'catalog',
    'skugrid',
    'infinite',
    'searchresult',
)

_PRODUCT_PATH_RE = re.compile(r'/product/[^?\s#]+', re.I)
_SKU_TAIL_RE = re.compile(r'-(\d{5,})(?:/|\?|$)')
_SKU_PATH_RE = re.compile(r'/product/(\d{5,})(?:/|\?|$)')

_BAD_NAMES = frozenset({
    'распродажа', 'sale', 'скидки', 'скидка', 'акция', 'хит', 'топ', 'новинка',
    'купить', 'в корзину', 'в избранное', 'цена что надо', 'суперцена',
})

_BAD_NAME_RE = re.compile(
    r'^(распродажа|sale|скидки?|акция|хит|топ|новинка|цена что надо|суперцена)\s*:?\s*$',
    re.I,
)


def is_composer_api_url(url: str) -> bool:
    u = (url or '').lower()
    return any(m in u for m in _COMPOSER_URL_MARKERS)


def _digits_price(text: str) -> int | None:
    if not text:
        return None
    s = str(text).replace('\u00a0', ' ').replace('\u2009', ' ')
    m = re.search(r'([\d\s]{2,})\s*[₽\u20bd]', s)
    if not m:
        m = re.search(r'(\d[\d\s]{3,})', s)
    if not m:
        return None
    digits = re.sub(r'\D', '', m.group(1))
    if not digits:
        return None
    try:
        val = int(digits)
    except ValueError:
        return None
    if 299 <= val <= 9_999_999:
        return val
    return None


def _price_from_value(val: Any, depth: int = 0) -> int | None:
    if depth > 8 or val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        n = int(val)
        if 299 <= n <= 9_999_999:
            return n
        return None
    if isinstance(val, str):
        return _digits_price(val)
    if isinstance(val, dict):
        for key in (
            'price', 'finalPrice', 'cardPrice', 'originalPrice', 'value', 'text',
            'minPrice', 'marketingPrice',
        ):
            if key in val:
                p = _price_from_value(val[key], depth + 1)
                if p:
                    return p
        for key in ('priceV2', 'prices', 'mainState'):
            if key in val:
                p = _price_from_value(val[key], depth + 1)
                if p:
                    return p
    if isinstance(val, list):
        for item in val:
            p = _price_from_value(item, depth + 1)
            if p:
                return p
    return None


def _title_from_value(val: Any, depth: int = 0) -> str:
    if depth > 8 or val is None:
        return ''
    if isinstance(val, str):
        s = val.strip()
        if len(s) >= 6 and s.lower() not in _BAD_NAMES:
            return s
        return ''
    if isinstance(val, dict):
        for key in ('title', 'name', 'text', 'value'):
            if key in val:
                t = _title_from_value(val[key], depth + 1)
                if t:
                    return t
        for key in ('mainState', 'atom', 'textAtom'):
            if key in val:
                t = _title_from_value(val[key], depth + 1)
                if t:
                    return t
    return ''


def _sku_from_link(link: str) -> str:
    if not link:
        return ''
    m = _SKU_TAIL_RE.search(link)
    if m:
        return m.group(1)
    m = _SKU_PATH_RE.search(link)
    return m.group(1) if m else ''


def normalize_product_url(link: str) -> str:
    raw = (link or '').strip()
    if not raw:
        return ''
    if raw.startswith('ozon://'):
        raw = 'https://www.ozon.ru' + raw[6:]
    if raw.startswith('//'):
        raw = 'https:' + raw
    if raw.startswith('/'):
        raw = 'https://www.ozon.ru' + raw
    if 'ozon.ru' not in raw.lower():
        return ''
    u = urlparse(raw)
    if '/product/' not in (u.path or ''):
        return ''
    return f'https://www.ozon.ru{u.path.rstrip("/")}/'


def _link_from_obj(obj: dict[str, Any]) -> str:
    for key in ('link', 'url', 'webUrl', 'productLink'):
        val = obj.get(key)
        if isinstance(val, str) and '/product/' in val:
            return normalize_product_url(val)
    action = obj.get('action')
    if isinstance(action, dict):
        for key in ('link', 'url', 'deeplink'):
            val = action.get(key)
            if isinstance(val, str) and '/product/' in val:
                return normalize_product_url(val)
    deeplink = obj.get('deeplink')
    if isinstance(deeplink, str) and '/product/' in deeplink:
        return normalize_product_url(deeplink.replace('ozon://', 'https://www.ozon.ru/'))
    return ''


def _sku_from_obj(obj: dict[str, Any], link: str) -> str:
    for key in ('sku', 'productId', 'id', 'itemId', 'skuId'):
        val = obj.get(key)
        if val is None:
            continue
        s = str(val).strip()
        if s.isdigit() and len(s) >= 5:
            return s
    return _sku_from_link(link)


def _image_from_obj(obj: dict[str, Any]) -> str:
    for key in ('image', 'imageUrl', 'coverImageUrl', 'preview'):
        val = obj.get(key)
        if isinstance(val, str) and val.startswith('http'):
            return val[:1024]
    images = obj.get('images')
    if isinstance(images, list):
        for item in images:
            if isinstance(item, str) and item.startswith('http'):
                return item[:1024]
    return ''


def is_valid_ozon_product_name(name: str) -> bool:
    s = re.sub(r'\s+', ' ', (name or '').replace('\u00a0', ' ')).strip()
    if len(s) < 6:
        return False
    low = s.lower()
    if low in _BAD_NAMES or _BAD_NAME_RE.match(low):
        return False
    if re.search(r'морков', low) and len(s) <= 24:
        return False
    if re.search(r'(балл\w*\s+за\s+отзыв|к[эе]шб[еэ]к)', low):
        return False
    return True


def _normalize_name(raw: str) -> str:
    s = re.sub(r'\s+', ' ', (raw or '').replace('\u00a0', ' ')).strip()
    if not is_valid_ozon_product_name(s):
        return ''
    return s


def _row_from_product_obj(obj: dict[str, Any]) -> dict[str, Any] | None:
    link = _link_from_obj(obj)
    if not link:
        return None
    sku = _sku_from_obj(obj, link)
    if not sku:
        return None
    name = _normalize_name(_title_from_obj(obj))
    if not name:
        name = _normalize_name(_title_from_value(obj.get('mainState')))
    if not name:
        try:
            slug = link.split('/product/')[-1].rsplit('-', 1)[0]
            name = _normalize_name(slug.replace('-', ' '))
        except Exception:
            name = ''
    if not name:
        return None
    price = _price_from_value(obj.get('price'))
    if price is None:
        price = _price_from_value(obj.get('priceV2'))
    if price is None:
        price = _price_from_value(obj.get('mainState'))
    if price is None:
        price = _price_from_value(obj)
    row: dict[str, Any] = {
        'name': name[:500],
        'url': link,
        'price': price,
        'old_price': None,
        'image_url': _image_from_obj(obj),
        'vendor_code': sku,
        'is_available': obj.get('isAvailable', obj.get('is_available', True)) is not False,
        'source': 'composer',
    }
    return row


def _title_from_obj(obj: dict[str, Any]) -> str:
    candidates: list[str] = []
    for key in ('title', 'name', 'productName', 'text', 'value'):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            candidates.append(val.strip())
    ms = obj.get('mainState')
    if isinstance(ms, dict):
        t = _title_from_value(ms)
        if t:
            candidates.append(t)
    best_latin = ''
    for raw in candidates:
        t = _normalize_name(raw)
        if not t:
            continue
        if re.search(r'[а-яё]', t, re.I):
            return t
        if not best_latin:
            best_latin = t
    return best_latin


def _walk_for_products(node: Any, acc: dict[str, dict[str, Any]], depth: int = 0) -> None:
    if depth > 30:
        return
    if isinstance(node, dict):
        link = _link_from_obj(node)
        sku_hint = _sku_from_obj(node, link) if link else ''
        has_price = _price_from_value(node) is not None
        has_title = bool(_title_from_obj(node) or _title_from_value(node.get('mainState')))
        if link and sku_hint and (has_price or has_title):
            row = _row_from_product_obj(node)
            if row and row.get('url'):
                url = row['url']
                prev = acc.get(url)
                if not prev or (row.get('price') and not prev.get('price')):
                    acc[url] = row
        for value in node.values():
            _walk_for_products(value, acc, depth + 1)
    elif isinstance(node, list):
        for item in node:
            _walk_for_products(item, acc, depth + 1)


def _parse_widget_state_raw(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_from_layout_widget_states(data: dict[str, Any], acc: dict[str, dict[str, Any]]) -> None:
    widget_states = data.get('widgetStates')
    layout = data.get('layout')
    if not isinstance(widget_states, dict):
        return

    state_ids: list[str] = []
    if isinstance(layout, list):
        for entry in layout:
            if not isinstance(entry, dict):
                continue
            component = str(entry.get('component') or '').lower()
            if any(h in component for h in _CATALOG_COMPONENT_HINTS):
                sid = entry.get('stateId')
                if isinstance(sid, str):
                    state_ids.append(sid)

    if not state_ids:
        state_ids = list(widget_states.keys())

    for sid in state_ids:
        raw = widget_states.get(sid)
        if isinstance(raw, str):
            state = _parse_widget_state_raw(raw)
            if state is not None:
                _walk_for_products(state, acc)
        elif isinstance(raw, dict):
            _walk_for_products(raw, acc)


def extract_products_from_composer(data: Any) -> list[dict[str, Any]]:
    acc: dict[str, dict[str, Any]] = {}
    if isinstance(data, dict):
        _extract_from_layout_widget_states(data, acc)
        _walk_for_products(data, acc)
    elif isinstance(data, list):
        for item in data:
            _walk_for_products(item, acc)
    rows = [r for r in acc.values() if r.get('url') and r.get('name')]
    priced = sum(1 for r in rows if r.get('price'))
    logger.debug('Ozon composer: %d товаров (%d с ценой)', len(rows), priced)
    return rows


class OzonComposerSniffer:

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        self._enabled = False
        self._seen_urls: set[str] = set()
        self._pending: dict[str, str] = {}

    def enable(self) -> None:
        if self._enabled:
            return
        try:
            self._driver.execute_cdp_cmd('Network.enable', {})
            self._enabled = True
        except Exception:
            logger.debug('Ozon: CDP Network.enable недоступен', exc_info=True)

    def reset_seen(self) -> None:
        self._seen_urls.clear()
        self._pending.clear()

    def drain(self) -> list[dict[str, Any]]:
        if not self._enabled:
            return []
        acc: dict[str, dict[str, Any]] = {}
        try:
            logs = self._driver.get_log('performance')
        except Exception:
            return []

        for entry in logs:
            try:
                msg = json.loads(entry['message'])['message']
            except (KeyError, json.JSONDecodeError, TypeError):
                continue
            method = msg.get('method') or ''
            params = msg.get('params') or {}

            if method == 'Network.responseReceived':
                response = params.get('response') or {}
                url = str(response.get('url') or '')
                status = int(response.get('status') or 0)
                if status == 200 and is_composer_api_url(url):
                    req_id = params.get('requestId')
                    if req_id:
                        self._pending[str(req_id)] = url
                continue

            if method != 'Network.loadingFinished':
                continue
            req_id = str(params.get('requestId') or '')
            url = self._pending.pop(req_id, '')
            if not url or url in self._seen_urls:
                continue
            body = self._read_response_body(req_id)
            if not body:
                continue
            self._seen_urls.add(url)
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                continue
            for row in extract_products_from_composer(payload):
                u = row.get('url') or ''
                if not u:
                    continue
                prev = acc.get(u)
                if not prev or (row.get('price') and not prev.get('price')):
                    acc[u] = row

        return list(acc.values())

    def _read_response_body(self, request_id: str) -> str:
        try:
            result = self._driver.execute_cdp_cmd(
                'Network.getResponseBody', {'requestId': request_id},
            )
        except Exception:
            return ''
        body = result.get('body') or ''
        if result.get('base64Encoded'):
            try:
                body = base64.b64decode(body).decode('utf-8', 'replace')
            except Exception:
                return ''
        return str(body)


_FETCH_COMPOSER_JS = r"""
const path = arguments[0];
const api = 'https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=' + encodeURIComponent(path);
return fetch(api, {credentials: 'include', headers: {accept: 'application/json'}})
  .then(function (r) { return r.ok ? r.json() : null; })
  .catch(function () { return null; });
"""


def fetch_composer_in_browser(driver: Any, page_url: str) -> list[dict[str, Any]]:
    u = urlparse(page_url)
    path = u.path or '/'
    if u.query:
        path = f'{path}?{u.query}'
    try:
        payload = driver.execute_script(_FETCH_COMPOSER_JS, path)
    except Exception:
        logger.debug('Ozon: fetch composer в браузере не удался', exc_info=True)
        return []
    if not payload:
        return []
    return extract_products_from_composer(payload)
