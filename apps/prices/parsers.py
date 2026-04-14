from __future__ import annotations

import importlib
import logging
import os
import random
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)


class DNSBlockedError(RuntimeError):
    pass


DNS_BLOCKED_MSG = (
    'DNS открыл страницу «доступ запрещён» (403): блокировка по IP/сети на стороне сайта, '
    'не из‑за headless. Попробуйте другую сеть, VPN с выходом в РФ, или прокси в PROXY_LIST. '
    'В курсовой допустимо описать ограничение парсинга публичного магазина.'
)


def _chrome_major_version() -> int | None:
    override = getattr(settings, 'CHROME_VERSION_MAIN', None)
    if override is not None:
        try:
            return int(override)
        except (TypeError, ValueError):
            pass
    if sys.platform == 'win32':
        try:
            import winreg

            for hive, path in (
                (winreg.HKEY_CURRENT_USER, r'Software\Google\Chrome\BLBeacon'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Google\Chrome\BLBeacon'),
            ):
                try:
                    key = winreg.OpenKey(hive, path)
                    try:
                        version, _ = winreg.QueryValueEx(key, 'version')
                    finally:
                        winreg.CloseKey(key)
                    return int(str(version).split('.')[0])
                except OSError:
                    continue
        except Exception:
            logger.debug('Не удалось прочитать версию Chrome из реестра', exc_info=True)
    return None

DNS_BASE_URL = 'https://www.dns-shop.ru'


def _chrome_user_agent() -> str:
    major = _chrome_major_version() or 131
    if sys.platform == 'win32':
        plat = 'Windows NT 10.0; Win64; x64'
    elif sys.platform == 'darwin':
        plat = 'Macintosh; Intel Mac OS X 10_15_7'
    else:
        plat = 'X11; Linux x86_64'
    return (
        f'Mozilla/5.0 ({plat}) AppleWebKit/537.36 (KHTML, like Gecko) '
        f'Chrome/{major}.0.0.0 Safari/537.36'
    )


def _noop_chrome_quit(*_a: Any, **_k: Any) -> None:
    return None


def _dns_page_blocked(title: str, src_head: str) -> bool:
    t = title or ''
    s = (src_head or '')[:12000]
    low = (t + '\n' + s).lower()
    if '403' in t.strip() or '403 error' in low[:800]:
        return True
    if 'forbidden' in t.lower():
        return True
    if 'http 403' in low:
        return True
    if 'доступ к сайту' in low and 'запрещ' in low:
        return True
    return False


@dataclass
class ParsedProduct:
    name: str
    price: int
    url: str
    vendor_code: str = ''
    image_url: str = ''
    old_price: int | None = None


def _parse_proxy_url(proxy: str) -> dict[str, Any]:
    """Parse proxy URL into components. Supports:
    - http://user:pass@host:port
    - socks5://user:pass@host:port
    - host:port  (no auth)
    """
    if '://' not in proxy:
        proxy = f'http://{proxy}'
    parsed = urlparse(proxy)
    return {
        'scheme': parsed.scheme or 'http',
        'host': parsed.hostname or '',
        'port': parsed.port or 3128,
        'username': parsed.username or '',
        'password': parsed.password or '',
    }


def _make_proxy_auth_extension(
    scheme: str, host: str, port: int, username: str, password: str,
) -> str:
    """Create a packed Chrome extension (.zip) that configures proxy with auth.
    Returns the path to the zip file.
    """
    manifest = (
        '{"version":"1.0.0","manifest_version":2,'
        '"name":"ProxyAuth","permissions":["proxy","tabs","unlimitedStorage",'
        '"storage","<all_urls>","webRequest","webRequestBlocking"],'
        '"background":{"scripts":["background.js"]},'
        '"minimum_chrome_version":"22.0.0"}'
    )

    background = """
var config = {
  mode: "fixed_servers",
  rules: {
    singleProxy: {scheme: "%s", host: "%s", port: %d},
    bypassList: ["localhost","127.0.0.1"]
  }
};
chrome.proxy.settings.set({value: config, scope: "regular"}, function(){});
chrome.webRequest.onAuthRequired.addListener(
  function(details) {
    return {authCredentials: {username: "%s", password: "%s"}};
  },
  {urls: ["<all_urls>"]},
  ['blocking']
);
""".strip() % (scheme, host, port, username, password)

    import zipfile
    ext_dir = tempfile.mkdtemp(prefix='proxy_auth_')
    zip_path = os.path.join(ext_dir, 'proxy_auth.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', manifest)
        zf.writestr('background.js', background)
    return zip_path


@dataclass
class DNSParser:
    headless: bool = True
    proxy: str | None = None
    max_retries: int = 3
    delay_min: float = 1.0
    delay_max: float = 3.0
    page_load_timeout: int = 30
    _driver: Any = field(default=None, init=False, repr=False)
    _uc: Any = field(default=None, init=False, repr=False)
    _by: Any = field(default=None, init=False, repr=False)
    _ec: Any = field(default=None, init=False, repr=False)
    _web_driver_wait: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.headless = getattr(settings, 'CHROME_HEADLESS', True)
        self.delay_min = getattr(settings, 'PARSE_DELAY_MIN', 1.0)
        self.delay_max = getattr(settings, 'PARSE_DELAY_MAX', 3.0)
        self.max_retries = getattr(settings, 'PARSE_MAX_RETRIES', 3)
        self.catalog_element_wait = int(getattr(settings, 'DNS_CATALOG_ELEMENT_WAIT', 60))
        self.page_load_timeout = int(getattr(settings, 'DNS_PAGE_LOAD_TIMEOUT', 60))
        self.catalog_scroll_max_rounds = int(getattr(settings, 'DNS_CATALOG_SCROLL_MAX_ROUNDS', 60))
        self.catalog_scroll_stable = int(getattr(settings, 'DNS_CATALOG_SCROLL_STABLE', 5))
        self.selenium_http_timeout = int(getattr(settings, 'DNS_SELENIUM_HTTP_TIMEOUT', 300))
        self._load_selenium_deps()

        proxy_list: list[str] = getattr(settings, 'PROXY_LIST', [])
        if proxy_list:
            self.proxy = random.choice(proxy_list)

    def _load_selenium_deps(self) -> None:
        try:
            self._uc = importlib.import_module('undetected_chromedriver')
            by_module = importlib.import_module('selenium.webdriver.common.by')
            self._ec = importlib.import_module('selenium.webdriver.support.expected_conditions')
            wait_module = importlib.import_module('selenium.webdriver.support.ui')
            self._by = by_module.By
            self._web_driver_wait = wait_module.WebDriverWait
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                'Missing parser dependency. Install selenium and undetected-chromedriver.'
            ) from exc

    def _build_driver(self) -> Any:
        options = self._uc.ChromeOptions()
        try:
            options.page_load_strategy = 'eager'
        except Exception:
            pass
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(f'--user-agent={_chrome_user_agent()}')

        self._proxy_ext_dir: str | None = None

        if self.proxy:
            pinfo = _parse_proxy_url(self.proxy)
            if pinfo['username'] and pinfo['password']:
                zip_path = _make_proxy_auth_extension(
                    pinfo['scheme'], pinfo['host'], pinfo['port'],
                    pinfo['username'], pinfo['password'],
                )
                self._proxy_ext_dir = os.path.dirname(zip_path)
                options.add_extension(zip_path)
                logger.info(
                    'Прокси с авторизацией (расширение): %s://%s:%s',
                    pinfo['scheme'], pinfo['host'], pinfo['port'],
                )
            else:
                proxy_addr = f'{pinfo["scheme"]}://{pinfo["host"]}:{pinfo["port"]}'
                options.add_argument(f'--proxy-server={proxy_addr}')
                logger.info('Используется прокси (без auth): %s', self.proxy)

        use_xvfb = self.headless and os.environ.get('DISPLAY')
        use_headless = self.headless and not use_xvfb

        ver_main = _chrome_major_version()
        uc_kwargs: dict[str, Any] = {'options': options, 'headless': use_headless}
        if ver_main is not None:
            uc_kwargs['version_main'] = ver_main
            logger.info('undetected_chromedriver version_main=%s', ver_main)
        if use_xvfb:
            logger.info(
                'Xvfb-режим: Chrome запущен как обычный браузер на виртуальном дисплее %s',
                os.environ['DISPLAY'],
            )
        elif use_headless:
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            logger.info('Headless-режим (без Xvfb)')

        driver = self._uc.Chrome(**uc_kwargs)
        to = float(self.page_load_timeout)
        driver.set_page_load_timeout(to)
        try:
            driver.set_script_timeout(to)
        except Exception:
            pass
        self._apply_driver_http_timeout(driver)
        return driver

    def _apply_driver_http_timeout(self, driver: Any) -> None:
        try:
            ce = driver.command_executor
            cfg = getattr(ce, '_client_config', None)
            if cfg is not None:
                cfg.timeout = float(self.selenium_http_timeout)
        except Exception:
            logger.debug('Не удалось задать HTTP-таймаут клиента WebDriver', exc_info=True)

    def _driver_get(self, driver: Any, url: str) -> None:
        te_mod = importlib.import_module('selenium.common.exceptions')
        try:
            driver.get(url)
        except te_mod.TimeoutException:
            logger.warning(
                'Таймаут загрузки страницы Chrome (%ss), останавливаем загрузку и продолжаем: %s',
                self.page_load_timeout,
                url,
            )
            try:
                driver.execute_script('window.stop();')
            except Exception:
                pass
        except te_mod.WebDriverException as exc:
            err = str(exc).lower()
            if 'err_connection_timed_out' in err or 'err_connection_reset' in err:
                logger.error('Таймаут соединения: %s', url)
            elif 'err_proxy' in err or 'proxy' in err and 'failed' in err:
                logger.error('Ошибка прокси: %s', url)
            raise

    def _get_driver(self) -> Any:
        if self._driver is None:
            self._driver = self._build_driver()
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            d = self._driver
            self._driver = None
            try:
                d.quit()
            except Exception:
                pass
            try:
                d.quit = _noop_chrome_quit
            except Exception:
                pass
        if getattr(self, '_proxy_ext_dir', None):
            try:
                shutil.rmtree(self._proxy_ext_dir, ignore_errors=True)
            except Exception:
                pass
            self._proxy_ext_dir = None

    def __enter__(self) -> DNSParser:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _random_delay(self) -> None:
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

    def _check_dns_blocked(self, driver: Any) -> None:
        te_mod = importlib.import_module('selenium.common.exceptions')
        title = ''
        src = ''
        try:
            title = (driver.title or '').strip()
            ps = driver.page_source
            if ps:
                src = ps[:12000]
        except (te_mod.NoSuchWindowException, te_mod.InvalidSessionIdException) as exc:
            logger.warning('Chrome: окно или сессия недоступны')
            raise exc
        except Exception:
            pass
        if _dns_page_blocked(title, src):
            raise DNSBlockedError(DNS_BLOCKED_MSG)

    def _navigate_dns_with_warmup(self, driver: Any, url: str) -> None:
        cur = ''
        try:
            cur = driver.current_url or ''
        except Exception:
            pass
        if 'dns-shop.ru' not in cur:
            try:
                self._driver_get(driver, f'{DNS_BASE_URL}/')
                time.sleep(random.uniform(2.0, 4.5))
            except Exception:
                logger.debug('Предварительный заход на главную DNS не удался', exc_info=True)
        self._driver_get(driver, url)
        time.sleep(2)
        self._check_dns_blocked(driver)

    def parse_category(self, dns_category_slug: str) -> list[ParsedProduct]:
        url = f'{DNS_BASE_URL}/catalog/{dns_category_slug}/'
        logger.info('Парсинг категории: %s', url)

        for attempt in range(1, self.max_retries + 1):
            try:
                return self._do_parse_category(url)
            except DNSBlockedError:
                raise
            except Exception as exc:
                logger.exception(
                    'Ошибка парсинга категории (попытка %d/%d): %s',
                    attempt, self.max_retries, url,
                )
                self.close()
                if attempt < self.max_retries:
                    backoff = 2 ** attempt + random.uniform(0, 1)
                    if 'err_connection_timed_out' in str(exc).lower():
                        extra = random.uniform(20.0, 45.0)
                        backoff += extra
                    logger.info('Повтор через %.1f сек.', backoff)
                    time.sleep(backoff)

        logger.error('Все попытки парсинга категории исчерпаны: %s', url)
        return []

    def _do_parse_category(self, url: str) -> list[ParsedProduct]:
        driver = self._get_driver()
        self._navigate_dns_with_warmup(driver, url)

        try:
            self._web_driver_wait(driver, self.catalog_element_wait).until(
                self._ec.presence_of_element_located((self._by.CLASS_NAME, 'catalog-product'))
            )
        except Exception:
            try:
                logger.error(
                    'Нет .catalog-product за %ss: url=%s title=%r',
                    self.catalog_element_wait,
                    driver.current_url,
                    driver.title,
                )
            except Exception:
                pass
            raise
        self._random_delay()

        self._scroll_to_load_all(driver)

        product_elements = driver.find_elements(self._by.CLASS_NAME, 'catalog-product')
        logger.info('Найдено элементов на странице: %d', len(product_elements))

        seen: dict[str, ParsedProduct] = {}

        for el in product_elements:
            try:
                parsed = self._extract_product_from_element(el)
                if parsed and parsed.url not in seen:
                    seen[parsed.url] = parsed
            except Exception:
                logger.debug('Не удалось извлечь товар из элемента', exc_info=True)
                continue

        products = list(seen.values())
        logger.info('Уникальных товаров после парсинга: %d', len(products))
        if product_elements and not products:
            try:
                sample_text = (product_elements[0].text or '').strip().replace('\n', ' ')
                sample_text = re.sub(r'\s+', ' ', sample_text)[:220]
            except Exception:
                sample_text = ''
            logger.warning(
                'Найдено %d карточек .catalog-product, но не удалось извлечь ни одного товара. '
                'Вероятно изменилась вёрстка карточки/цены. Пример текста первой карточки: %r',
                len(product_elements),
                sample_text,
            )
        return products

    def _click_catalog_more(self, driver: Any) -> bool:
        for sel in (
            'button.catalog-more__button',
            '.catalog-more__button',
            '[data-role="catalog-more"]',
            'button.catalog-category__more',
        ):
            try:
                el = driver.find_element(self._by.CSS_SELECTOR, sel)
                if el.is_displayed() and el.is_enabled():
                    driver.execute_script('arguments[0].click();', el)
                    return True
            except Exception:
                pass
        for label in ('Показать ещё', 'Показать еще', 'Показать больше'):
            try:
                xp = (
                    f"//button[contains(normalize-space(.), '{label}')]"
                    f"|//a[contains(normalize-space(.), '{label}')]"
                )
                for el in driver.find_elements(self._by.XPATH, xp):
                    if el.is_displayed() and el.is_enabled():
                        driver.execute_script('arguments[0].click();', el)
                        return True
            except Exception:
                pass
        return False

    def _scroll_catalog_js(self, driver: Any) -> None:
        driver.execute_script(
            """
            var h = Math.max(
                document.body ? document.body.scrollHeight : 0,
                document.documentElement.scrollHeight
            );
            window.scrollTo(0, h);
            var first = document.querySelector('.catalog-product');
            if (!first) return;
            var el = first.parentElement;
            while (el && el !== document.body && el !== document.documentElement) {
                var st = window.getComputedStyle(el);
                var oy = st.overflowY;
                if ((oy === 'auto' || oy === 'scroll' || oy === 'overlay')
                    && el.scrollHeight > el.clientHeight + 40) {
                    el.scrollTop = el.scrollHeight;
                }
                el = el.parentElement;
            }
            """
        )

    def _scroll_to_load_all(self, driver: Any) -> None:
        stable = 0
        max_r = max(1, self.catalog_scroll_max_rounds)
        need_stable = max(1, self.catalog_scroll_stable)
        for round_i in range(max_r):
            prev = len(driver.find_elements(self._by.CLASS_NAME, 'catalog-product'))
            self._scroll_catalog_js(driver)
            time.sleep(random.uniform(1.0, 1.8))
            self._scroll_catalog_js(driver)
            time.sleep(random.uniform(0.6, 1.2))
            cur = len(driver.find_elements(self._by.CLASS_NAME, 'catalog-product'))
            if cur > prev:
                stable = 0
                logger.debug('Каталог DNS: +%s карточек (всего %s)', cur - prev, cur)
                continue
            if self._click_catalog_more(driver):
                stable = 0
                time.sleep(random.uniform(1.5, 2.5))
                continue
            stable += 1
            if stable >= need_stable:
                logger.info(
                    'Подгрузка каталога завершена: карточек в DOM %s '
                    '(%s раундов подряд без роста; на сайте может быть больше позиций '
                    '«всего в разделе», чем карточек в выдаче).',
                    cur,
                    need_stable,
                )
                break
        else:
            logger.warning(
                'Достигнут лимит раундов прокрутки (%s), карточек в DOM: %s. '
                'При необходимости увеличьте DNS_CATALOG_SCROLL_MAX_ROUNDS.',
                max_r,
                len(driver.find_elements(self._by.CLASS_NAME, 'catalog-product')),
            )

    def parse_product(self, product_url: str) -> ParsedProduct | None:
        logger.info('Парсинг товара: %s', product_url)

        for attempt in range(1, self.max_retries + 1):
            try:
                return self._do_parse_product(product_url)
            except DNSBlockedError:
                raise
            except Exception:
                logger.exception(
                    'Ошибка парсинга товара (попытка %d/%d): %s',
                    attempt, self.max_retries, product_url,
                )
                self.close()
                if attempt < self.max_retries:
                    backoff = 2 ** attempt + random.uniform(0, 1)
                    time.sleep(backoff)

        logger.error('Все попытки парсинга товара исчерпаны: %s', product_url)
        return None

    def _do_parse_product(self, product_url: str) -> ParsedProduct | None:
        driver = self._get_driver()
        self._navigate_dns_with_warmup(driver, product_url)
        self._random_delay()

        self._web_driver_wait(driver, self.catalog_element_wait).until(
            self._ec.presence_of_element_located((self._by.CLASS_NAME, 'product-card-top'))
        )

        name = self._safe_text(driver, 'product-card-top__title')
        if not name:
            return None

        price = self._extract_price(driver, 'product-buy__price')
        if price is None:
            return None

        old_price = self._extract_price(driver, 'product-buy__prev')

        vendor_code = ''
        try:
            vc_el = driver.find_element(self._by.CLASS_NAME, 'product-card-top__code')
            vc_text = vc_el.text.strip()
            match = re.search(r'(\d+)', vc_text)
            if match:
                vendor_code = match.group(1)
        except Exception:
            pass

        image_url = ''
        try:
            img = driver.find_element(self._by.CSS_SELECTOR, '.product-images-slider__main-img img')
            image_url = img.get_attribute('src') or ''
        except Exception:
            pass

        return ParsedProduct(
            name=name,
            price=price,
            url=product_url,
            vendor_code=vendor_code,
            image_url=image_url,
            old_price=old_price,
        )

    def _extract_product_from_element(self, el: Any) -> ParsedProduct | None:
        name_el = self._find_first_element(
            el,
            (
                (self._by.CLASS_NAME, 'catalog-product__name'),
                (self._by.CSS_SELECTOR, 'a.catalog-product__name'),
                (self._by.CSS_SELECTOR, 'a[data-role="product-link"]'),
                (self._by.CSS_SELECTOR, 'a[href*="/product/"]'),
            ),
        )
        if name_el is None:
            return None
        name = (name_el.text or '').strip()
        link = name_el.get_attribute('href') or ''

        if not name or not link:
            return None

        price = None
        for cls in ('product-buy__price', 'catalog-product__price', 'ui-kit-price__main'):
            price = self._extract_price_from_element(el, cls)
            if price is not None:
                break
        if price is None:
            # Резервный вариант: ищем любой блок с символом рубля в тексте карточки.
            candidates = el.find_elements(self._by.XPATH, ".//*[contains(text(),'₽')]")
            for c in candidates:
                price = self._clean_price(c.text or c.get_attribute('textContent') or '')
                if price is not None:
                    break
        if price is None:
            return None

        old_price = None
        for cls in ('product-buy__prev', 'catalog-product__old-price', 'ui-kit-price__old'):
            old_price = self._extract_price_from_element(el, cls)
          
            if old_price is not None:
                break

        image_url = ''
        try:
            img = el.find_element(self._by.CSS_SELECTOR, '.catalog-product__image img')
            image_url = img.get_attribute('src') or img.get_attribute('data-src') or ''
        except Exception:
            pass

        vendor_code = ''
        try:
            code_el = el.find_element(self._by.CLASS_NAME, 'catalog-product__code')
            match = re.search(r'(\d+)', code_el.text)
            if match:
                vendor_code = match.group(1)
        except Exception:
            pass

        return ParsedProduct(
            name=name,
            price=price,
            url=link,
            vendor_code=vendor_code,
            image_url=image_url,
            old_price=old_price,
        )

    @staticmethod
    def _find_first_element(parent: Any, selectors: tuple[tuple[Any, str], ...]) -> Any | None:
        for by, sel in selectors:
            try:
                return parent.find_element(by, sel)
            except Exception:
                continue
        return None

    @staticmethod
    def _extract_price(driver: Any, class_name: str) -> int | None:
        try:
            by = importlib.import_module('selenium.webdriver.common.by').By
            el = driver.find_element(by.CLASS_NAME, class_name)
            return DNSParser._clean_price(el.get_attribute('textContent'))
        except Exception:
            return None

    @staticmethod
    def _extract_price_from_element(parent: Any, class_name: str) -> int | None:
        try:
            by = importlib.import_module('selenium.webdriver.common.by').By
            el = parent.find_element(by.CLASS_NAME, class_name)
            return DNSParser._clean_price(el.get_attribute('textContent'))
        except Exception:
            return None

    @staticmethod
    def _clean_price(raw: str) -> int | None:
        cleaned = raw.split('₽')[0].strip()
        cleaned = re.sub(r'\s+', '', cleaned)
        cleaned = re.sub(r'[^\d]', '', cleaned)
        if cleaned.isdigit():
            return int(cleaned)
        return None

    @staticmethod
    def _safe_text(driver: Any, class_name: str) -> str:
        try:
            by = importlib.import_module('selenium.webdriver.common.by').By
            el = driver.find_element(by.CLASS_NAME, class_name)
            return el.text.strip()
        except Exception:
            return ''
