from __future__ import annotations

import json
import logging
import time
from typing import Any

from django.conf import settings

from .base_parser import BaseParser
from .parsers import ChromeDriverMixin, ParsedProduct

logger = logging.getLogger(__name__)

MVIDEO_BASE = 'https://www.mvideo.ru'
MVIDEO_PRODUCTS_BFF = f'{MVIDEO_BASE}/bff/products'
MVIDEO_IMG_BASE = 'https://img.mvideo.ru/'

# In-page POST к BFF выполняется ИЗ контекста открытой вкладки mvideo.ru:
# запрос уходит с куками/фингерпринтом реального браузера, прошедшего WAF.
# Прямой requests без этого контекста отдаёт antibot-страницу (проверено).
_BFF_POST_JS = r"""
const [url, body] = arguments;
const done = arguments[arguments.length - 1];
fetch(url, {
  method: 'POST',
  credentials: 'include',
  headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
  body: body,
}).then(r => r.text().then(t => done({status: r.status, text: t})))
  .catch(e => done({status: -1, text: '', error: String(e)}));
"""


class MVideoBlockedError(Exception):
    """WAF M.Video не пустил (antibot-страница вместо JSON)."""


class MVideoParser(ChromeDriverMixin, BaseParser):
    """Парсер M.Video.

    M.Video закрыт WAF, который блокирует прямые HTTP-запросы к BFF-API.
    Поэтому мы поднимаем реальный Chrome (как у Citilink/DNS — очередь
    parsing_heavy), один раз заходим на главную для WAF-клиренса, а дальше
    дёргаем JSON-эндпоинт `POST /bff/products` ИЗ контекста страницы через
    fetch(). На выходе — чистый структурированный JSON с ценами, без парсинга
    HTML.

    `parse_category` принимает seoCategoryId (числовой суффикс в URL категории
    M.Video, напр. '205' для смартфонов) — он лежит в CategoryListing.external_path
    для source='mvideo'.
    """

    def __init__(self) -> None:
        default_headless = bool(getattr(settings, 'CHROME_HEADLESS', True))
        self._init_chrome_runtime(
            page_timeout_setting='MVIDEO_PAGE_LOAD_TIMEOUT',
            page_timeout_default=60,
            headless_setting='MVIDEO_HEADLESS',
            headless_default=default_headless,
            user_data_dir_setting='MVIDEO_USER_DATA_DIR',
        )
        self._page_size = int(getattr(settings, 'MVIDEO_PAGE_SIZE', 60))
        self._max_pages = int(getattr(settings, 'MVIDEO_MAX_PAGES', 60))
        self._script_timeout = int(getattr(settings, 'MVIDEO_BFF_TIMEOUT', 40))
        self._page_delay = float(getattr(settings, 'MVIDEO_PAGE_DELAY', 0.8))
        self._cleared = False

    def _ensure_clearance(self) -> None:
        """Один раз зайти на главную, чтобы Chrome получил WAF-куки."""
        if self._cleared:
            return
        driver = self._get_driver()
        try:
            driver.set_page_load_timeout(self.page_load_timeout)
        except Exception:
            pass
        try:
            driver.set_script_timeout(self._script_timeout)
        except Exception:
            pass
        logger.info('M.Video: захожу на главную для WAF-клиренса')
        driver.get(MVIDEO_BASE + '/')
        time.sleep(5)
        title = (driver.title or '').strip()
        if not title:
            raise MVideoBlockedError('M.Video: пустой title после загрузки главной (возможен WAF)')
        self._cleared = True

    def _bff_products(self, seo_category_id: str, cursor_id: str) -> dict[str, Any]:
        body = json.dumps({
            'limit': self._page_size,
            'cursorId': cursor_id,
            'enrich': True,
            'filters': [{'id': 'category', 'valuesId': [str(seo_category_id)]}],
            'sortBy': 'popularity',
            'sortDirection': 'desc',
            'isGettingBonusRoubles': True,
        })
        driver = self._get_driver()
        res = driver.execute_async_script(_BFF_POST_JS, MVIDEO_PRODUCTS_BFF, body)
        status = res.get('status')
        text = res.get('text') or ''
        if status != 200:
            head = text[:200]
            raise MVideoBlockedError(
                f'M.Video BFF /products вернул status={status} '
                f'(err={res.get("error")}) head={head!r}'
            )
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise MVideoBlockedError(
                f'M.Video BFF: не JSON в ответе (WAF?): head={text[:200]!r}'
            ) from exc
        if not data.get('success'):
            raise MVideoBlockedError(
                f'M.Video BFF success=false: {json.dumps(data)[:200]}'
            )
        return data.get('body') or {}

    def parse_category(self, category_url: str) -> list[ParsedProduct]:
        seo_category_id = (category_url or '').strip()
        if not seo_category_id:
            logger.warning('M.Video: пустой seoCategoryId')
            return []

        self._ensure_clearance()

        result: dict[str, ParsedProduct] = {}
        cursor_id = ''
        total: int | None = None

        for page in range(1, self._max_pages + 1):
            body = self._bff_products(seo_category_id, cursor_id)
            items = body.get('items') or []
            if total is None:
                total = body.get('total')
            for raw in items:
                parsed = self._map_item(raw)
                if parsed is not None:
                    result[parsed.url] = parsed

            next_cursor = str(body.get('cursorId') or '')
            logger.info(
                'M.Video кат.%s: страница %d, товаров на странице %d, '
                'всего уникальных %d (total в категории: %s)',
                seo_category_id, page, len(items), len(result), total,
            )

            if not items or not next_cursor or next_cursor == cursor_id:
                logger.info('M.Video кат.%s: конец категории на странице %d', seo_category_id, page)
                break
            cursor_id = next_cursor
            time.sleep(self._page_delay)

        logger.info('M.Video кат.%s: итого уникальных товаров %d', seo_category_id, len(result))
        return list(result.values())

    @staticmethod
    def _build_image_url(images: Any) -> str:
        if not images or not isinstance(images, list):
            return ''
        path = str(images[0] or '').strip()
        if not path:
            return ''
        if path.startswith('http'):
            return path
        return MVIDEO_IMG_BASE + path.lstrip('/')

    def _map_item(self, raw: dict[str, Any]) -> ParsedProduct | None:
        product_id = str(raw.get('productId') or '').strip()
        name = (raw.get('name') or '').strip()
        slug = (raw.get('slug') or '').strip()
        if not product_id or not name or not slug:
            return None

        price_obj = raw.get('price') or {}
        sale = price_obj.get('salePrice')
        base = price_obj.get('basePrice')
        if sale is None:
            # Нет цены (товар недоступен/снят) — пропускаем, цену сохранять нечего.
            return None
        try:
            price = int(round(float(sale)))
        except (TypeError, ValueError):
            return None

        old_price: int | None = None
        try:
            if base is not None and float(base) > float(sale):
                old_price = int(round(float(base)))
        except (TypeError, ValueError):
            old_price = None

        url = MVIDEO_BASE + slug if slug.startswith('/') else f'{MVIDEO_BASE}/{slug}'
        is_available = not bool(raw.get('soldOut'))

        return ParsedProduct(
            name=name,
            price=price,
            url=url,
            vendor_code=product_id,
            image_url=self._build_image_url(raw.get('images')),
            old_price=old_price,
            is_available=is_available,
            extra={
                'product_id': product_id,
                'rating': raw.get('rating'),
                'discount': price_obj.get('discount'),
            },
        )
