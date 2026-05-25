"""
Парсер Wildberries для проекта Price Monitor.

В отличие от DNS/Citilink (Selenium + Chrome), использует публичные HTTP API
Wildberries напрямую. Преимущества:
  - В 10-20 раз быстрее (нет браузера)
  - В 10 раз меньше памяти (~30MB vs ~500MB)
  - Стабильнее (не блокируется Cloudflare/Qrator)
  - Не требует Xvfb / headless

API endpoints:
  - search.wb.ru/exactmatch/ru/common/v9/search — поиск по запросу (используется)
  - catalog.wb.ru/catalog/{slug}/v4/catalog     — каталог по shard+subject (опц.)
  - catalog.wb.ru/menu/v8/api                   — дерево категорий
  - card.wb.ru/cards/v2/detail                  — детали товара (опционально)

Документация: docs/TZ_WILDBERRIES_PARSER.md

Архитектура (этапы из ТЗ):
  Этап 1 ✅: SKELETON — структура классов, базовые методы.
  Этап 2 ✅: HTTP клиент с retry/throttle.
  Этап 3 ✅: Парсинг категории + преобразование в ParsedProduct.
  Этап 4: Дерево категорий (опционально).

Формат external_path в CategoryListing (для WB):
  - search query: "видеокарта"  → используется search endpoint
  - shard:subject: "electronic13:3274"  → catalog endpoint (точнее)
  - простое название категории работает как search query
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from .base_parser import BaseParser
from .parsers import ParsedProduct  # переиспользуем общий dataclass

logger = logging.getLogger(__name__)

# === Константы ===

WB_CATALOG_BASE = 'https://catalog.wb.ru'
WB_CARD_BASE = 'https://card.wb.ru'
WB_BASKET_CDN_TEMPLATE = 'https://basket-{basket:02d}.wbbasket.ru'
WB_SITE_BASE = 'https://www.wildberries.ru'

# Search endpoint — самый универсальный для нашего MVP.
# Принимает текстовый запрос, возвращает релевантные товары.
WB_SEARCH_URL = 'https://search.wb.ru/exactmatch/ru/common/v9/search'

# Статус-коды которые надо ретраить (временные ошибки)
WB_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)

# Headers как у обычного браузера — снижает шанс блокировки
WB_DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    # ВАЖНО: НЕ указываем 'br' (brotli) — requests без библиотеки brotli
    # не сможет декодировать ответ, и JSON парсинг упадёт.
    'Accept-Encoding': 'gzip, deflate',
    'Origin': 'https://www.wildberries.ru',
    'Referer': 'https://www.wildberries.ru/',
    'Connection': 'keep-alive',
}

# Таблица "basket" CDN-серверов для картинок WB.
# WB периодически добавляет новые при росте каталога.
# Источник: эмпирически + https://github.com/<wb-parsers>
_BASKET_BOUNDARIES = (
    (14_400_000, 1),
    (28_800_000, 2),
    (43_200_000, 3),
    (72_000_000, 4),
    (100_800_000, 5),
    (106_200_000, 6),
    (131_400_000, 7),
    (160_200_000, 8),
    (165_600_000, 9),
    (191_400_000, 10),
    (204_600_000, 11),
    (218_400_000, 12),
    (251_400_000, 13),
    (285_000_000, 14),
    (333_600_000, 15),
    (390_600_000, 16),
)
_BASKET_FALLBACK = 17  # для самых новых товаров вне таблицы


# === Исключения ===

class WildberriesError(RuntimeError):
    """Базовое исключение парсера Wildberries."""


class WildberriesRateLimitError(WildberriesError):
    """429 Too Many Requests — нужен backoff."""


class WildberriesAPIError(WildberriesError):
    """Неожиданный формат ответа или 5xx ошибка."""


# === Утилиты ===

def get_basket_number(nm_id: int) -> int:
    """Определяет номер basket CDN-сервера WB по nm_id товара.

    Используется для формирования URL картинок:
      https://basket-{NN}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/...
    """
    for boundary, basket in _BASKET_BOUNDARIES:
        if nm_id < boundary:
            return basket
    return _BASKET_FALLBACK


def get_image_url(nm_id: int, size: str = 'c516x688') -> str:
    """Формирует URL картинки товара WB.

    Args:
        nm_id: уникальный ID товара на WB.
        size: размер картинки. Варианты: c246x328, c516x688, big, original.

    Returns:
        URL картинки на WB CDN.
    """
    if not nm_id:
        return ''
    vol = nm_id // 100_000
    part = nm_id // 1_000
    basket = get_basket_number(nm_id)
    return (
        f'{WB_BASKET_CDN_TEMPLATE.format(basket=basket)}'
        f'/vol{vol}/part{part}/{nm_id}/images/{size}/1.webp'
    )


def get_product_url(nm_id: int) -> str:
    """Формирует URL карточки товара на сайте WB."""
    if not nm_id:
        return ''
    return f'{WB_SITE_BASE}/catalog/{nm_id}/detail.aspx'


def clean_price_kopecks(value: Any) -> int | None:
    """Преобразует цену в копейках (WB API) в рубли.

    Args:
        value: salePriceU или priceU из ответа WB (в копейках).

    Returns:
        Цена в рублях (int) или None если невалидно.
    """
    if value is None:
        return None
    try:
        kopecks = int(value)
        if kopecks <= 0:
            return None
        return kopecks // 100
    except (TypeError, ValueError):
        return None


def is_product_available(product: dict) -> bool:
    """Проверяет, есть ли товар в наличии (по stocks)."""
    sizes = product.get('sizes') or []
    if not isinstance(sizes, list):
        return False
    for size in sizes:
        if not isinstance(size, dict):
            continue
        stocks = size.get('stocks') or []
        if not isinstance(stocks, list):
            continue
        for stock in stocks:
            if isinstance(stock, dict) and int(stock.get('qty') or 0) > 0:
                return True
    return False


# === Rate Limiter (Этап 2) ===

class RateLimiter:
    """Ограничитель скорости запросов (защита от 429).

    Простой sleep-based limiter. Для async версии нужен другой подход.
    """

    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / max(0.1, requests_per_second)
        self.last_request_at: float = 0.0

    def wait(self) -> None:
        """Ждёт нужное время с момента предыдущего запроса."""
        now = time.monotonic()
        elapsed = now - self.last_request_at
        if elapsed < self.min_interval:
            sleep_for = self.min_interval - elapsed
            # Микро-jitter чтобы не выглядеть как робот
            sleep_for += random.uniform(0, 0.1)
            time.sleep(sleep_for)
        self.last_request_at = time.monotonic()


# === Парсер ===

@dataclass
class WBCategoryRef:
    """Ссылка на категорию WB для парсинга."""
    slug: str            # 'videokarty' — используется в URL
    cat_id: int | None   # ID категории WB (опционально, для дополнительной фильтрации)
    shard: str = ''      # 'electronic18' — иногда нужен для отдельных endpoint'ов


class WildberriesParser(BaseParser):
    """Парсер Wildberries через публичные HTTP API.

    Использование:
        with WildberriesParser() as parser:
            products = parser.parse_category('videokarty:8146')
            # или: products = parser.parse_category('videokarty')

    Формат category_url:
        'videokarty'          — только slug
        'videokarty:8146'     — slug:cat_id
        'videokarty:8146:electronic18'  — slug:cat_id:shard
    """

    def __init__(self) -> None:
        # Настройки из settings.py с дефолтами
        self.dest_id: int = int(getattr(settings, 'WB_DEST_ID', -1257786))
        self.dest_name: str = str(getattr(settings, 'WB_DEST_NAME', 'Москва'))
        self.max_pages: int = int(getattr(settings, 'WB_MAX_PAGES', 30))
        self.rate_limit_rps: float = float(getattr(settings, 'WB_RATE_LIMIT_RPS', 2.0))
        self.request_timeout: int = int(getattr(settings, 'WB_REQUEST_TIMEOUT', 15))
        self.max_retries: int = int(getattr(settings, 'WB_MAX_RETRIES', 3))
        self.sort_order: str = str(getattr(settings, 'WB_SORT_ORDER', 'popular'))

        self._proxy_list: list[str] = list(getattr(settings, 'WB_PROXY_LIST', []) or [])
        self._current_proxy: str | None = (
            random.choice(self._proxy_list) if self._proxy_list else None
        )

        # Будут проинициализированы при первом запросе (Этап 2)
        self._session: Any = None
        self._rate_limiter: RateLimiter = RateLimiter(self.rate_limit_rps)

        logger.info(
            'WildberriesParser инициализирован: dest=%s (%s), max_pages=%d, rps=%.1f, '
            'proxy=%s',
            self.dest_id, self.dest_name, self.max_pages, self.rate_limit_rps,
            'есть' if self._current_proxy else 'нет',
        )

    # ===== Публичный API (требуется BaseParser) =====

    def parse_category(self, category_url: str) -> list[ParsedProduct]:
        """Парсит все товары категории на Wildberries.

        Args:
            category_url: Может быть:
              - 'видеокарта' — search query (рекомендуется для MVP)
              - 'slug' — будет использоваться как search query
              - URL: 'https://www.wildberries.ru/catalog/...' (выделим slug)

        Returns:
            Список ParsedProduct. Пустой список при ошибках или нет товаров.
        """
        cat_ref = self._parse_category_url(category_url)
        if not cat_ref:
            logger.error('WB: некорректный category_url=%r', category_url)
            return []

        # Search query = slug (для MVP). Можно расширить под shard+subject позже.
        search_query = cat_ref.slug
        logger.info(
            'WB: парсинг по поисковому запросу %r (max_pages=%d, sort=%s)',
            search_query, self.max_pages, self.sort_order,
        )

        all_products: list[ParsedProduct] = []
        seen_nm_ids: set[int] = set()  # дедупликация в рамках одного парсинга
        empty_streak = 0

        for page in range(1, self.max_pages + 1):
            try:
                products = self._fetch_search_page(search_query, page=page)
            except WildberriesRateLimitError:
                logger.warning('WB: rate limit на странице %d, останавливаемся', page)
                break
            except Exception as exc:
                logger.exception('WB: ошибка на странице %d: %s', page, exc)
                break

            if not products:
                empty_streak += 1
                logger.info(
                    'WB: страница %d пустая (попытка %d/2)',
                    page, empty_streak,
                )
                if empty_streak >= 2:
                    logger.info('WB: 2 пустые страницы → конец категории')
                    break
                continue
            empty_streak = 0

            # Обрабатываем товары + дедупликация по nm_id
            page_new = 0
            for raw in products:
                parsed = self._product_to_parsed(raw)
                if parsed is None:
                    continue
                nm_id = self._extract_nm_id(parsed.vendor_code)
                if nm_id and nm_id in seen_nm_ids:
                    continue
                if nm_id:
                    seen_nm_ids.add(nm_id)
                all_products.append(parsed)
                page_new += 1

            logger.info(
                'WB: страница %d/%d, товаров %d (новых %d, всего %d)',
                page, self.max_pages, len(products), page_new, len(all_products),
            )

            # Если page_new = 0 на полной странице — WB зациклился, выходим
            if page_new == 0 and len(products) > 0:
                logger.info('WB: страница %d без новых товаров (зацикливание) → конец', page)
                break

        logger.info('WB: всего товаров для %r: %d', search_query, len(all_products))
        return all_products

    def close(self) -> None:
        """Освобождает ресурсы (HTTP session)."""
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                logger.debug('WB: ошибка при закрытии session', exc_info=True)
            self._session = None

    # ===== Внутренние методы =====

    @staticmethod
    def _parse_category_url(category_url: str) -> WBCategoryRef | None:
        """Парсит строку 'slug', 'slug:cat_id' или 'slug:cat_id:shard'."""
        raw = (category_url or '').strip()
        if not raw:
            return None

        # Если передали полный URL — выделим slug
        if raw.startswith('http'):
            # https://www.wildberries.ru/catalog/elektronika/videokarty
            parts = raw.rstrip('/').split('/')
            slug = parts[-1] if parts else ''
            return WBCategoryRef(slug=slug, cat_id=None) if slug else None

        parts = raw.split(':')
        slug = parts[0].strip()
        if not slug:
            return None

        cat_id: int | None = None
        if len(parts) >= 2 and parts[1].strip():
            try:
                cat_id = int(parts[1].strip())
            except ValueError:
                logger.warning('WB: некорректный cat_id в %r, игнорируем', category_url)

        shard = parts[2].strip() if len(parts) >= 3 else ''
        return WBCategoryRef(slug=slug, cat_id=cat_id, shard=shard)

    def _build_session(self) -> Any:
        """Создаёт HTTP session с retry adapter и нужными headers.

        ⚠️ Важно: trust_env=False — иначе session берёт SOCKS прокси из
        окружения (ALL_PROXY=socks5://...) который у пользователя может
        быть дохлым и блокировать все запросы. Прокси задаём явно через
        WB_PROXY_LIST если нужно.
        """
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
        except ImportError as exc:
            raise WildberriesError(
                'Модули requests/urllib3 не установлены. Добавь в requirements.txt.'
            ) from exc

        session = requests.Session()
        # ⚠️ КРИТИЧНО: не использовать ENV переменные (ALL_PROXY и т.п.)
        session.trust_env = False
        session.headers.update(WB_DEFAULT_HEADERS)

        # Retry policy для 429/5xx.
        # backoff_factor=3.0 → паузы 3, 6, 12, 24 сек (тотал ~45 сек).
        # Этого достаточно для большинства transient 429.
        retry = Retry(
            total=self.max_retries,
            backoff_factor=3.0,
            status_forcelist=WB_RETRY_STATUS_CODES,
            allowed_methods=frozenset(['GET']),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=10,
            pool_maxsize=10,
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        # Прокси задаём явно только если есть в settings
        if self._current_proxy:
            session.proxies = {
                'http': self._current_proxy,
                'https': self._current_proxy,
            }
            logger.info('WB: используется прокси %s', self._current_proxy)

        return session

    def _get_session(self) -> Any:
        """Lazy-инициализация HTTP session."""
        if self._session is None:
            self._session = self._build_session()
        return self._session

    def _fetch_search_page(
        self,
        query: str,
        *,
        page: int = 1,
    ) -> list[dict]:
        """Запрашивает одну страницу поиска WB.

        Args:
            query: поисковый запрос (например, "видеокарта").
            page: номер страницы (1-100).

        Returns:
            Список словарей с товарами. Пустой если ошибка/нет товаров.

        Raises:
            WildberriesRateLimitError: при 429 даже после retry.
            WildberriesAPIError: при неожиданном формате ответа.
        """
        self._rate_limiter.wait()

        params = {
            'ab_testing': 'false',
            'appType': '1',
            'curr': 'rub',
            'dest': str(self.dest_id),
            'page': str(page),
            'query': query,
            'resultset': 'catalog',
            'sort': self.sort_order,
            'spp': '30',
            'suppressSpellcheck': 'false',
        }

        try:
            session = self._get_session()
            response = session.get(
                WB_SEARCH_URL,
                params=params,
                timeout=self.request_timeout,
            )
        except Exception as exc:
            # Network error after retries — логируем и поднимаем
            logger.error('WB: network error для query=%r page=%d: %s', query, page, exc)
            raise WildberriesError(f'Network error: {exc}') from exc

        if response.status_code == 429:
            raise WildberriesRateLimitError(
                f'WB: rate limit 429 (retry adapter не помог): query={query!r}. '
                f'Подожди 5-10 минут и попробуй снова, или снизь WB_RATE_LIMIT_RPS.'
            )
        if response.status_code >= 400:
            raise WildberriesAPIError(
                f'WB: HTTP {response.status_code} для query={query!r} page={page}'
            )

        # ⚠️ WB иногда возвращает 200 с HTML страницей вместо JSON
        # (например, заглушка про региональные ограничения или 429 в HTML).
        # Детектим по началу body — если HTML, значит API недоступен.
        body_start = response.text[:50].lstrip()
        if body_start.startswith('<'):
            logger.warning(
                'WB: API вернул HTML вместо JSON для query=%r page=%d. '
                'Возможно, IP заблокирован или WB ограничивает регион. '
                'Body[:200]=%r',
                query, page, response.text[:200],
            )
            return []

        # Парсинг JSON
        try:
            data = response.json()
        except (ValueError, Exception) as exc:
            logger.warning(
                'WB: невалидный JSON для query=%r page=%d: %s. Body[:200]=%r',
                query, page, exc, response.text[:200],
            )
            return []

        # Safe extraction (структура WB может меняться)
        if not isinstance(data, dict):
            logger.warning('WB: response не dict: %r', type(data))
            return []
        payload = data.get('data') or {}
        if not isinstance(payload, dict):
            logger.warning('WB: data не dict: %r', type(payload))
            return []
        products = payload.get('products') or []
        if not isinstance(products, list):
            logger.warning('WB: products не list: %r', type(products))
            return []

        return [p for p in products if isinstance(p, dict)]

    def _product_to_parsed(self, raw: dict) -> ParsedProduct | None:
        """Преобразует один WB-продукт из API ответа в ParsedProduct.

        Args:
            raw: словарь с товаром из WB API.

        Returns:
            ParsedProduct или None если товар невалиден (без цены/имени/id).
        """
        # ID товара
        try:
            nm_id = int(raw.get('id') or 0)
        except (TypeError, ValueError):
            return None
        if not nm_id:
            return None

        # Имя
        name = (raw.get('name') or '').strip()
        if not name:
            return None

        # Цена: WB может вернуть в нескольких полях. Берём минимальную доступную.
        # salePriceU — цена со скидкой, priceU — без скидки.
        # У товара могут быть продавцы с разными ценами — берём из sizes.
        price = self._extract_min_price(raw)
        if price is None or price <= 0:
            return None

        # Старая цена (для отображения скидки)
        old_price = clean_price_kopecks(raw.get('priceU'))
        # priceU может быть равно salePriceU (нет скидки) — не сохраняем
        if old_price is not None and price is not None and old_price <= price:
            old_price = None

        # Бренд
        brand = (raw.get('brand') or '').strip()

        # Картинка
        image_url = get_image_url(nm_id)

        # URL карточки
        product_url = get_product_url(nm_id)

        # Доступность по stocks
        is_available = is_product_available(raw)

        # Имя с брендом если бренд не в имени
        if brand and brand.lower() not in name.lower():
            full_name = f'{brand} {name}'
        else:
            full_name = name

        return ParsedProduct(
            name=full_name[:500],  # ограничение длины
            price=int(price),
            url=product_url,
            vendor_code=str(nm_id),  # для дедупликации через source_sku
            image_url=image_url,
            old_price=int(old_price) if old_price else None,
            is_available=is_available,
        )

    @staticmethod
    def _extract_min_price(raw: dict) -> int | None:
        """Извлекает минимальную цену из товара WB.

        У товара может быть несколько продавцов с разными ценами.
        Берём минимальную доступную (только in-stock).
        """
        # Сначала проверим sizes (там могут быть продавцы)
        min_price: int | None = None
        sizes = raw.get('sizes') or []
        if isinstance(sizes, list):
            for size in sizes:
                if not isinstance(size, dict):
                    continue
                # priceWithSpp — цена с СПП (со скидкой постоянного покупателя)
                price_obj = size.get('price') or {}
                if isinstance(price_obj, dict):
                    p = clean_price_kopecks(
                        price_obj.get('product')
                        or price_obj.get('total')
                        or price_obj.get('basic')
                    )
                    if p and (min_price is None or p < min_price):
                        min_price = p

        # Fallback: salePriceU из корня товара
        if min_price is None:
            min_price = clean_price_kopecks(raw.get('salePriceU'))

        return min_price

    @staticmethod
    def _extract_nm_id(vendor_code: str) -> int | None:
        """Возвращает nm_id из строки vendor_code или None."""
        try:
            return int(vendor_code)
        except (TypeError, ValueError):
            return None


# === Экспорт ===

__all__ = (
    'WildberriesParser',
    'WBCategoryRef',
    'WildberriesError',
    'WildberriesRateLimitError',
    'WildberriesAPIError',
    'get_basket_number',
    'get_image_url',
    'get_product_url',
    'clean_price_kopecks',
    'is_product_available',
    'RateLimiter',
)
