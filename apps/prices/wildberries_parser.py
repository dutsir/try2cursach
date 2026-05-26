"""
Парсер Wildberries для проекта Price Monitor.

В отличие от DNS/Citilink (Selenium + Chrome), использует публичные HTTP API
Wildberries напрямую. Преимущества:
  - В 10-20 раз быстрее (нет браузера)
  - В 10 раз меньше памяти (~30MB vs ~500MB)
  - Стабильнее (не блокируется Cloudflare/Qrator)
  - Не требует Xvfb / headless

API endpoints:
  - catalog.wb.ru/catalog/{shard}/catalog       — каталог по shard+query (ОСНОВНОЙ)
  - search.wb.ru/exactmatch/ru/common/v9/search — поиск по запросу (FALLBACK)
  - static-basket-01.wbbasket.ru/.../main-menu  — дерево категорий

Документация: docs/TZ_WILDBERRIES_PARSER.md

Формат external_path в CategoryListing (для WB):
  - catalog режим (точный):   "shard:electronic18|query:cat=3274"
  - search режим (fallback):  "видеокарта" или "videokarty"
  Catalog режим определяется по наличию префикса "shard:" в строке.
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

# Search endpoint (FALLBACK для категорий без shard/query)
WB_SEARCH_URL = 'https://search.wb.ru/exactmatch/ru/common/v9/search'

# Catalog endpoint (ОСНОВНОЙ — точные товары категории по shard+query)
# Шаблон: https://catalog.wb.ru/catalog/{shard}/v4/catalog?...&{query}
# v4 — актуальная версия (2024-2025), проверено через прямой curl.
WB_CATALOG_URL_TEMPLATE = 'https://catalog.wb.ru/catalog/{shard}/v4/catalog'

# Главное меню WB — дерево всех категорий с shard и query параметрами.
# Источник: https://github.com/kirillignatyev/wildberries-parser-in-python (актуально на 2024-11).
WB_MENU_URL = 'https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v3.json'

# Cache key для дерева категорий (Redis через django cache).
WB_MENU_CACHE_KEY = 'wb:catalog_tree:v3'

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
# Обновлено 2025-05-26 через live-probing wb-api для nm_id из разных диапазонов.
# Базовая таблица: github.com/Duff89/wildberries_parser (vol ≤ 2405).
# Расширение basket-16..41: probing самых популярных категорий + линейная
# интерполяция между точными samples (vol 3385→20, 4324→24, 5607→29,
# 6765→33, 8532→38, 9979→41).
# При 404 — фронтенд должен иметь fallback (или периодически перепроверять).
# Boundary семантика: товары с nm_id < boundary → этот basket.
# Каждая boundary = первый nm_id СЛЕДУЮЩЕГО basket.
# Proved-точки — из live probing 2025-05-26 (vol→basket пары):
#   1177→09, 2363→15, 3329→20, 3385→20, 3995→23, 4324→24, 4917→27,
#   5204→28, 5344→28, 5607→29, 5643→29, 6765→33, 8532→38, 8631→38,
#   8960→39, 9979→41
# Между proved точками — линейная интерполяция.
_BASKET_BOUNDARIES = (
    (14_400_000, 1),
    (28_800_000, 2),
    (43_200_000, 3),
    (72_000_000, 4),
    (100_800_000, 5),
    (106_200_000, 6),
    (111_600_000, 7),
    (117_000_000, 8),
    (131_400_000, 9),    # proved 1177→09 (Duff: upper=1313)
    (160_200_000, 10),
    (165_600_000, 11),
    (192_000_000, 12),
    (204_600_000, 13),
    (219_000_000, 14),
    (240_600_000, 15),   # proved 2363→15 (Duff: upper=2405)
    (265_100_000, 16),
    (289_600_000, 17),
    (314_100_000, 18),
    (332_900_000, 19),   # proved 3329→20
    (362_000_000, 20),   # proved 3385→20
    (385_500_000, 21),
    (399_500_000, 22),   # proved 3995→23
    (432_400_000, 23),   # proved 4324→24
    (452_100_000, 24),
    (471_800_000, 25),
    (491_700_000, 26),   # proved 4917→27
    (520_400_000, 27),   # proved 5204→28
    (560_700_000, 28),   # proved 5607→29, 5643→29
    (589_600_000, 29),
    (618_500_000, 30),
    (647_400_000, 31),
    (676_500_000, 32),   # proved 6765→33
    (711_900_000, 33),
    (747_300_000, 34),
    (782_700_000, 35),
    (818_100_000, 36),
    (853_200_000, 37),   # proved 8532→38, 8631→38
    (896_000_000, 38),   # proved 8960→39
    (947_000_000, 39),
    (997_900_000, 40),   # proved 9979→41
    (1_500_000_000, 41),
)
_BASKET_FALLBACK = 42  # для свежих товаров вне таблицы


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
    """Проверяет, есть ли товар в наличии.

    v4 (2024+): если есть хотя бы один size с валидной ценой — доступен.
    Старая схема (fallback): проверяем sizes[].stocks[].qty.
    """
    sizes = product.get('sizes') or []
    if not isinstance(sizes, list):
        return False
    for size in sizes:
        if not isinstance(size, dict):
            continue
        # v4: наличие = есть price.product > 0
        price_obj = size.get('price') or {}
        if isinstance(price_obj, dict):
            p = price_obj.get('product') or price_obj.get('total')
            if p and int(p) > 0:
                return True
        # Старая схема: stocks
        stocks = size.get('stocks') or []
        if isinstance(stocks, list):
            for stock in stocks:
                if isinstance(stock, dict) and int(stock.get('qty') or 0) > 0:
                    return True
    return False


# === Дерево категорий WB (main-menu) ===

def _flatten_wb_menu(nodes: Any, out: list[dict]) -> None:
    """Рекурсивно сплющивает дерево категорий WB в плоский список.

    Каждая нода содержит: name, url, shard (опц.), query (опц.), childs (опц.).
    Берём ноды у которых есть и shard и query — это листья по которым можно парсить.
    Но также сохраняем все ноды с url (для поиска по slug).
    """
    if isinstance(nodes, list):
        for n in nodes:
            _flatten_wb_menu(n, out)
        return
    if not isinstance(nodes, dict):
        return
    entry = {
        'name': nodes.get('name', ''),
        'url': nodes.get('url', ''),
        'shard': nodes.get('shard', '') or '',
        'query': nodes.get('query', '') or '',
    }
    if entry['name']:
        out.append(entry)
    childs = nodes.get('childs')
    if isinstance(childs, list):
        _flatten_wb_menu(childs, out)


def download_wb_catalog_tree(*, force_refresh: bool = False) -> list[dict]:
    """Скачивает дерево категорий WB с кэшированием через Django cache (Redis).

    Args:
        force_refresh: если True — игнорирует кэш и качает заново.

    Returns:
        Плоский список словарей с полями: name, url, shard, query.

    Кэшируется на WB_CATEGORIES_CACHE_TTL (по умолчанию 24 часа).
    """
    if not force_refresh:
        try:
            from django.core.cache import cache
            cached = cache.get(WB_MENU_CACHE_KEY)
            if cached:
                return cached
        except Exception as exc:
            logger.debug('WB menu cache read error: %s', exc)

    try:
        import requests
    except ImportError as exc:
        raise WildberriesError('requests не установлен') from exc

    logger.info('WB: качаю дерево категорий с %s', WB_MENU_URL)
    sess = requests.Session()
    sess.trust_env = False
    sess.headers.update(WB_DEFAULT_HEADERS)
    response = sess.get(WB_MENU_URL, timeout=30)
    response.raise_for_status()
    raw = response.json()

    flat: list[dict] = []
    _flatten_wb_menu(raw, flat)
    logger.info('WB: дерево категорий загружено, %d записей', len(flat))

    try:
        from django.conf import settings as _settings
        from django.core.cache import cache
        ttl = int(getattr(_settings, 'WB_CATEGORIES_CACHE_TTL', 86400))
        cache.set(WB_MENU_CACHE_KEY, flat, timeout=ttl)
    except Exception as exc:
        logger.debug('WB menu cache write error: %s', exc)

    return flat


def find_category_in_tree(
    query: str,
    tree: list[dict] | None = None,
) -> dict | None:
    """Находит категорию WB по slug, имени или URL.

    Args:
        query: slug ('processory'), имя ('Процессоры') или часть URL.
        tree: дерево (если None — будет скачано).

    Returns:
        dict с полями name/url/shard/query, либо None.
        Возвращает первое совпадение приоритезируя точное совпадение по URL/slug.
    """
    if tree is None:
        tree = download_wb_catalog_tree()
    q = (query or '').strip().lower()
    if not q:
        return None

    exact_url: dict | None = None
    exact_name: dict | None = None
    contains_url: dict | None = None
    contains_name: dict | None = None

    for entry in tree:
        if not entry.get('shard') or not entry.get('query'):
            continue
        name_low = entry.get('name', '').lower()
        url_low = entry.get('url', '').lower()
        url_slug = url_low.rstrip('/').rsplit('/', 1)[-1]

        if url_slug == q:
            exact_url = entry
            break
        if name_low == q:
            exact_name = exact_name or entry
        if q in url_low:
            contains_url = contains_url or entry
        if q in name_low:
            contains_name = contains_name or entry

    return exact_url or exact_name or contains_url or contains_name


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
    """Ссылка на категорию WB для парсинга.

    Режимы:
      catalog — точный парсинг через catalog.wb.ru (нужны shard + query)
      search  — fallback через search.wb.ru (нужен только search_query)
    """
    mode: str  # 'catalog' or 'search'
    shard: str = ''
    query: str = ''           # catalog query string: 'cat=3274&kind=2'
    search_query: str = ''    # search query: 'видеокарта'


class WildberriesParser(BaseParser):
    """Парсер Wildberries через публичные HTTP API.

    Использование:
        with WildberriesParser() as parser:
            # Catalog режим (рекомендуется — точные результаты):
            products = parser.parse_category('shard:electronic18|query:cat=3274')

            # Search режим (fallback):
            products = parser.parse_category('видеокарта')
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
            category_url: формат:
              - catalog режим: 'shard:electronic18|query:cat=3274'
              - search режим:  'видеокарта' или 'videokarty'

        Returns:
            Список ParsedProduct. Пустой при ошибках/отсутствии товаров.
        """
        cat_ref = self._parse_category_url(category_url)
        if not cat_ref:
            logger.error('WB: некорректный category_url=%r', category_url)
            return []

        if cat_ref.mode == 'catalog':
            logger.info(
                'WB: catalog mode shard=%s query=%s max_pages=%d sort=%s',
                cat_ref.shard, cat_ref.query, self.max_pages, self.sort_order,
            )
            fetch_fn = lambda page: self._fetch_catalog_page(
                cat_ref.shard, cat_ref.query, page=page,
            )
            label = f'catalog[{cat_ref.shard}]'
        else:
            logger.info(
                'WB: search mode query=%r max_pages=%d sort=%s',
                cat_ref.search_query, self.max_pages, self.sort_order,
            )
            fetch_fn = lambda page: self._fetch_search_page(
                cat_ref.search_query, page=page,
            )
            label = f'search[{cat_ref.search_query}]'

        all_products: list[ParsedProduct] = []
        seen_nm_ids: set[int] = set()
        empty_streak = 0

        for page in range(1, self.max_pages + 1):
            try:
                products = fetch_fn(page)
            except WildberriesRateLimitError:
                logger.warning('WB: rate limit на странице %d, останавливаемся', page)
                break
            except Exception as exc:
                logger.exception('WB: ошибка на странице %d: %s', page, exc)
                break

            if not products:
                empty_streak += 1
                logger.info('WB: %s страница %d пустая (%d/2)', label, page, empty_streak)
                if empty_streak >= 2:
                    logger.info('WB: %s — 2 пустые подряд, конец', label)
                    break
                continue
            empty_streak = 0

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
                'WB: %s страница %d/%d, товаров %d (новых %d, всего %d)',
                label, page, self.max_pages, len(products), page_new, len(all_products),
            )

            if page_new == 0 and len(products) > 0:
                logger.info('WB: %s страница %d без новых → конец', label, page)
                break

        logger.info('WB: %s — всего товаров: %d', label, len(all_products))
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
        """Парсит external_path в WBCategoryRef.

        Catalog режим:  'shard:electronic18|query:cat=3274&kind=2'
        Search режим:   'видеокарта' или 'videokarty' (любой текст без 'shard:')

        Возвращает None если строка пустая.
        """
        raw = (category_url or '').strip()
        if not raw:
            return None

        # Catalog режим — обязательны и shard и query
        if 'shard:' in raw and 'query:' in raw:
            shard = ''
            query = ''
            for part in raw.split('|'):
                p = part.strip()
                if p.startswith('shard:'):
                    shard = p[len('shard:'):].strip()
                elif p.startswith('query:'):
                    query = p[len('query:'):].strip()
            if shard and query:
                return WBCategoryRef(mode='catalog', shard=shard, query=query)
            logger.warning('WB: формат catalog некорректен (нет shard/query): %r', raw)

        # Полный URL — извлечём slug для search
        if raw.startswith('http'):
            parts = raw.rstrip('/').split('/')
            slug = parts[-1] if parts else ''
            if slug:
                return WBCategoryRef(mode='search', search_query=slug)
            return None

        # Search режим — вся строка как query
        return WBCategoryRef(mode='search', search_query=raw)

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

    def _fetch_catalog_page(
        self,
        shard: str,
        query: str,
        *,
        page: int = 1,
    ) -> list[dict]:
        """Запрашивает одну страницу каталога WB через catalog.wb.ru.

        Это ОСНОВНОЙ endpoint (точные товары категории, не поиск).
        URL: catalog.wb.ru/catalog/{shard}/catalog?appType=1&...&{query}

        Args:
            shard: ID шарда (например 'electronic18').
            query: query string из main-menu (например 'cat=3274&kind=2').
            page: номер страницы (1..max_pages).

        Returns:
            Список словарей с товарами.

        Raises:
            WildberriesRateLimitError: 429 после retry.
            WildberriesAPIError: 5xx или некорректный JSON.
        """
        self._rate_limiter.wait()

        url = WB_CATALOG_URL_TEMPLATE.format(shard=shard)
        # Базовые параметры (порядок важен для некоторых instance'ов WB)
        base_params = [
            ('appType', '1'),
            ('curr', 'rub'),
            ('dest', str(self.dest_id)),
            ('page', str(page)),
            ('sort', self.sort_order),
            ('spp', '30'),
        ]
        # query — это уже сформированная query string из main-menu,
        # склеиваем напрямую через '&'
        base_qs = '&'.join(f'{k}={v}' for k, v in base_params)
        full_url = f'{url}?{base_qs}&{query}'

        try:
            session = self._get_session()
            response = session.get(full_url, timeout=self.request_timeout)
        except Exception as exc:
            logger.error(
                'WB catalog: network error shard=%s query=%s page=%d: %s',
                shard, query, page, exc,
            )
            raise WildberriesError(f'Network error: {exc}') from exc

        if response.status_code == 429:
            raise WildberriesRateLimitError(
                f'WB catalog: rate limit 429 shard={shard} page={page}'
            )
        if response.status_code >= 400:
            raise WildberriesAPIError(
                f'WB catalog: HTTP {response.status_code} shard={shard} page={page}'
            )

        body_start = response.text[:50].lstrip()
        if body_start.startswith('<'):
            logger.warning(
                'WB catalog: API вернул HTML shard=%s page=%d. Body[:200]=%r',
                shard, page, response.text[:200],
            )
            return []

        try:
            data = response.json()
        except Exception as exc:
            logger.warning(
                'WB catalog: невалидный JSON shard=%s page=%d: %s',
                shard, page, exc,
            )
            return []

        return self._extract_products_from_response(data)

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

        return self._extract_products_from_response(data)

    @staticmethod
    def _extract_products_from_response(data: Any) -> list[dict]:
        """Универсальное извлечение products из ответа WB.

        Старая схема:  {"data": {"products": [...]}}
        Новая v4 (2024+): {"products": [...], "total": N}
        """
        if not isinstance(data, dict):
            return []
        # Новая v4: products на верхнем уровне
        products = data.get('products')
        if isinstance(products, list):
            return [p for p in products if isinstance(p, dict)]
        # Старая: внутри data
        payload = data.get('data') or {}
        if isinstance(payload, dict):
            products = payload.get('products') or []
            if isinstance(products, list):
                return [p for p in products if isinstance(p, dict)]
        return []

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

        # Цена: WB v4 хранит цену в sizes[].price.product (текущая) и .basic (старая).
        # Старая схема (на случай fallback): priceU/salePriceU на верхнем уровне.
        price, old_price = self._extract_prices(raw)
        if price is None or price <= 0:
            return None

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

        # Расширенные WB-специфичные поля для Offer.extra_metadata
        extra: dict[str, Any] = {}

        def _int_or_none(v: Any) -> int | None:
            try:
                return int(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        def _float_or_none(v: Any) -> float | None:
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        rating = _float_or_none(raw.get('rating') or raw.get('reviewRating'))
        if rating is not None:
            extra['rating'] = rating
        feedbacks = _int_or_none(raw.get('feedbacks'))
        if feedbacks is not None:
            extra['reviews_count'] = feedbacks
        if brand:
            extra['brand'] = brand[:100]
        brand_id = _int_or_none(raw.get('brandId'))
        if brand_id is not None:
            extra['brand_id'] = brand_id
        sale = _int_or_none(raw.get('sale'))
        if sale is not None and sale > 0:
            extra['sale_percent'] = sale
        elif old_price and price and old_price > price:
            # v4: WB не отдаёт 'sale' напрямую, вычисляем из basic/product
            extra['sale_percent'] = round((old_price - price) / old_price * 100)
        cashback = _int_or_none(raw.get('feedbackPoints'))
        if cashback is not None and cashback > 0:
            extra['cashback_percent'] = cashback
        supplier = (raw.get('supplier') or '').strip()
        if supplier:
            extra['supplier'] = supplier[:200]
        supplier_rating = _float_or_none(raw.get('supplierRating'))
        if supplier_rating is not None:
            extra['supplier_rating'] = supplier_rating

        return ParsedProduct(
            name=full_name[:500],  # ограничение длины
            price=int(price),
            url=product_url,
            vendor_code=str(nm_id),  # для дедупликации через source_sku
            image_url=image_url,
            old_price=int(old_price) if old_price else None,
            is_available=is_available,
            extra=extra,
        )

    @staticmethod
    def _extract_prices(raw: dict) -> tuple[int | None, int | None]:
        """Извлекает (текущую цену, старую цену) товара WB.

        v4 (2024+): sizes[].price.product (текущая), sizes[].price.basic (старая)
        Старая схема (fallback): salePriceU / priceU на верхнем уровне.

        Возвращает (price, old_price) в рублях.
        """
        cur: int | None = None
        old: int | None = None

        sizes = raw.get('sizes') or []
        if isinstance(sizes, list):
            for size in sizes:
                if not isinstance(size, dict):
                    continue
                price_obj = size.get('price') or {}
                if not isinstance(price_obj, dict):
                    continue
                p = clean_price_kopecks(
                    price_obj.get('product')
                    or price_obj.get('total')
                )
                b = clean_price_kopecks(price_obj.get('basic'))
                if p and (cur is None or p < cur):
                    cur = p
                if b and (old is None or b < old):
                    old = b

        # Fallback на старую схему
        if cur is None:
            cur = clean_price_kopecks(raw.get('salePriceU'))
        if old is None:
            old = clean_price_kopecks(raw.get('priceU'))

        # Скрываем старую цену если не больше текущей
        if old is not None and cur is not None and old <= cur:
            old = None

        return cur, old

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
    'download_wb_catalog_tree',
    'find_category_in_tree',
    'get_basket_number',
    'get_image_url',
    'get_product_url',
    'clean_price_kopecks',
    'is_product_available',
    'RateLimiter',
)
