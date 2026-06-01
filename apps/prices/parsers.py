from __future__ import annotations

import importlib
import json
import logging
import os
import random
import re
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

from .base_parser import BaseParser

logger = logging.getLogger(__name__)


DNS_BASE_URL = 'https://www.dns-shop.ru'


# Скрипт, который инжектится в КАЖДУЮ новую страницу через CDP
# (Page.addScriptToEvaluateOnNewDocument) ДО выполнения скриптов сайта.
# Назначение: DNS подгружает цены и часть карточек только когда страница
# «видима» (document.visibilityState === 'visible' и document.hasFocus()).
# Если Chrome запущен с off-screen окном, минимизирован или потерял фокус,
# visibilityState становится 'hidden' / 'prerender', JS-обработчики цен
# не срабатывают, и парсер получает карточки без цен.
#
# Подменяем геттеры document.hidden / visibilityState / hasFocus так, чтобы
# страница всегда считала окно активным. Дополнительно ловим события
# visibilitychange/blur/focus и предотвращаем их распространение, иначе
# фронт-скрипты DNS успевают «зарегистрировать» уход в фон и встают на паузу.
_DNS_FORCE_FOREGROUND_JS = r"""
(function () {
  try {
    Object.defineProperty(document, 'hidden', {
      configurable: true, get: function () { return false; }
    });
    Object.defineProperty(document, 'visibilityState', {
      configurable: true, get: function () { return 'visible'; }
    });
    Object.defineProperty(document, 'webkitHidden', {
      configurable: true, get: function () { return false; }
    });
    Object.defineProperty(document, 'webkitVisibilityState', {
      configurable: true, get: function () { return 'visible'; }
    });
    document.hasFocus = function () { return true; };
  } catch (e) {}
  // Глушим события blur/visibilitychange — они выключают JS-таймеры DNS.
  var BAD = ['blur', 'visibilitychange', 'webkitvisibilitychange',
             'pagehide', 'freeze'];
  for (var i = 0; i < BAD.length; i++) {
    (function (name) {
      window.addEventListener(name, function (e) {
        e.stopImmediatePropagation();
      }, true);
      document.addEventListener(name, function (e) {
        e.stopImmediatePropagation();
      }, true);
    })(BAD[i]);
  }
})();
"""


# Имитация активности пользователя: программные mousemove + focus + scroll.
# Запускается после загрузки страницы, чтобы «разбудить» отложенные
# обработчики, которые DNS вешает на первый interaction.
_DNS_NUDGE_ACTIVITY_JS = r"""
(function () {
  try { window.focus(); } catch (e) {}
  try {
    var ev = new MouseEvent('mousemove', {
      bubbles: true, cancelable: true,
      clientX: 100 + Math.random() * 400,
      clientY: 200 + Math.random() * 400
    });
    document.dispatchEvent(ev);
    document.body && document.body.dispatchEvent(ev);
  } catch (e) {}
  try {
    document.dispatchEvent(new Event('visibilitychange'));
  } catch (e) {}
})();
"""


# Анти-детект слой для Qrator. Инжектится через CDP ДО скриптов сайта на
# каждую новую страницу. undetected_chromedriver убирает базовые «вебдрайвер»-
# признаки, но Qrator проверяет глубже: язык, плагины, WebGL-рендерер
# (под Xvfb это SwiftShader/llvmpipe — явный признак бота), window.chrome,
# permissions API. Маскируем эти признаки под обычный десктопный Chrome в РФ.
# Помогает, когда Qrator отдаёт JS-челлендж (а не жёсткий сетевой 403):
# страница проходит проверку и получает clearance-куку.
_DNS_STEALTH_JS = r"""
(function () {
  function def(obj, prop, val) {
    try { Object.defineProperty(obj, prop, { configurable: true, get: function () { return val; } }); }
    catch (e) {}
  }
  // navigator.webdriver → undefined
  try { def(navigator, 'webdriver', undefined); } catch (e) {}
  // Языки: русскоязычный десктоп
  def(navigator, 'languages', ['ru-RU', 'ru', 'en-US', 'en']);
  // Непустой список плагинов (headless/чистый профиль выдаёт пустой)
  try {
    var fakePlugins = [
      { name: 'Chrome PDF Plugin' },
      { name: 'Chrome PDF Viewer' },
      { name: 'Native Client' }
    ];
    def(navigator, 'plugins', fakePlugins);
    def(navigator, 'mimeTypes', [{ type: 'application/pdf' }]);
  } catch (e) {}
  // window.chrome.runtime — присутствует в реальном Chrome
  try {
    if (!window.chrome) { window.chrome = {}; }
    if (!window.chrome.runtime) { window.chrome.runtime = {}; }
  } catch (e) {}
  // permissions.query для notifications не должен «выдавать» автоматизацию
  try {
    var origQuery = navigator.permissions && navigator.permissions.query;
    if (origQuery) {
      navigator.permissions.query = function (params) {
        if (params && params.name === 'notifications') {
          return Promise.resolve({ state: Notification.permission });
        }
        return origQuery.call(navigator.permissions, params);
      };
    }
  } catch (e) {}
  // WebGL: прячем SwiftShader/llvmpipe (Xvfb-рендерер) под обычную видеокарту
  try {
    var spoofGL = function (proto) {
      if (!proto) { return; }
      var getParam = proto.getParameter;
      proto.getParameter = function (p) {
        if (p === 37445) { return 'Intel Inc.'; }            // UNMASKED_VENDOR_WEBGL
        if (p === 37446) { return 'Intel Iris OpenGL Engine'; } // UNMASKED_RENDERER_WEBGL
        return getParam.call(this, p);
      };
    };
    spoofGL(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
    spoofGL(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
  } catch (e) {}
  // hardwareConcurrency/deviceMemory — правдоподобные значения десктопа
  try { def(navigator, 'hardwareConcurrency', 8); } catch (e) {}
  try { def(navigator, 'deviceMemory', 8); } catch (e) {}
})();
"""


# Проверка: на странице есть хотя бы N карточек с реальными ценами.
# Используется как условие готовности перед извлечением.
# Возвращает {cards: <всего>, priced: <с ценой>}.
_DNS_PRICE_READY_JS = r"""
return (function () {
  var cards = document.getElementsByClassName('catalog-product');
  var priced = 0;
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i];
    var hasClass =
      c.getElementsByClassName('product-buy__price').length > 0 ||
      c.getElementsByClassName('catalog-product__price').length > 0 ||
      c.getElementsByClassName('ui-kit-price__main').length > 0;
    if (hasClass) { priced++; continue; }
    // fallback: ищем символ рубля
    if ((c.innerText || c.textContent || '').indexOf('₽') !== -1) {
      priced++;
    }
  }
  return { cards: cards.length, priced: priced };
})();
"""


DNS_BLOCKED_MSG = (
    'DNS открыл страницу «доступ запрещён» (403): блокировка по IP/сети на стороне сайта, '
    'не из‑за headless. Попробуйте другую сеть, VPN с выходом в РФ, или прокси в PROXY_LIST. '
    'В курсовой допустимо описать ограничение парсинга публичного магазина.'
)


class DNSBlockedError(RuntimeError):
    pass


_DNS_CATALOG_CARDS_EXTRACT_JS = r"""
return (function () {
  function cleanPrice(raw) {
    if (!raw) return null;
    var s = String(raw).split('\u20bd')[0].trim().replace(/\s+/g, '').replace(/[^\d]/g, '');
    return /^\d+$/.test(s) ? parseInt(s, 10) : null;
  }
  function cardIsAvailable(card) {
    if (card.className && /--out-of-stock|--not-available|--sold-out/i.test(card.className)) {
      return false;
    }
    var t = (card.innerText || '').toLowerCase();
    if (t.indexOf('нет в наличии') !== -1) return false;
    if (t.indexOf('снят с производства') !== -1) return false;
    return true;
  }
  function extractFromCard(card) {
    var nameEl = card.querySelector('a.catalog-product__name')
      || card.querySelector('a[data-role="product-link"]')
      || card.querySelector('a[href*="/product/"]');
    if (!nameEl) return null;
    var name = (nameEl.innerText || '').trim();
    var link = nameEl.href || nameEl.getAttribute('href') || '';
    if (!name || !link) return null;

    var price = null;
    var priceClasses = ['product-buy__price', 'catalog-product__price', 'ui-kit-price__main'];
    for (var i = 0; i < priceClasses.length; i++) {
      var pe = card.getElementsByClassName(priceClasses[i])[0];
      if (pe) {
        price = cleanPrice(pe.textContent || '');
        if (price != null) break;
      }
    }
    if (price == null) {
      try {
        var xr = document.evaluate(
          ".//*[contains(., '\u20bd')]",
          card,
          null,
          XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
          null
        );
        for (var j = 0; j < xr.snapshotLength; j++) {
          var n = xr.snapshotItem(j);
          price = cleanPrice(n.textContent || '');
          if (price != null) break;
        }
      } catch (e) {}
    }
    if (price == null) return null;

    var oldPrice = null;
    var oldClasses = ['product-buy__prev', 'catalog-product__old-price', 'ui-kit-price__old'];
    for (var k = 0; k < oldClasses.length; k++) {
      var oe = card.getElementsByClassName(oldClasses[k])[0];
      if (oe) {
        oldPrice = cleanPrice(oe.textContent || '');
        if (oldPrice != null) break;
      }
    }

    var imageUrl = '';
    var img = card.querySelector('.catalog-product__image img');
    if (img) {
      imageUrl = img.getAttribute('src') || img.getAttribute('data-src') || '';
    }

    var vendorCode = '';
    var codeEl = card.getElementsByClassName('catalog-product__code')[0];
    if (codeEl) {
      var m = (codeEl.textContent || '').match(/(\d+)/);
      if (m) vendorCode = m[1];
    }

    return {
      name: name,
      url: link,
      price: price,
      old_price: oldPrice,
      image_url: imageUrl,
      vendor_code: vendorCode,
      is_available: cardIsAvailable(card)
    };
  }

  var cards = document.getElementsByClassName('catalog-product');
  var out = [];
  for (var c = 0; c < cards.length; c++) {
    var row = extractFromCard(cards[c]);
    if (row) out.push(row);
  }
  return out;
})();
"""


@dataclass
class ParsedProduct:
    name: str
    price: int
    url: str
    vendor_code: str = ''
    image_url: str = ''
    old_price: int | None = None
    is_available: bool = True
    extra: dict = field(default_factory=dict)


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


_PROFILE_LOCK_FILES = (
    'SingletonLock',
    'SingletonSocket',
    'SingletonCookie',
    'lockfile',
    os.path.join('Default', 'lockfile'),
)


def _clean_stale_profile_locks(profile_dir: str) -> None:
    if not profile_dir or not os.path.isdir(profile_dir):
        return
    removed: list[str] = []
    for rel in _PROFILE_LOCK_FILES:
        path = os.path.join(profile_dir, rel)
        try:
            if os.path.exists(path) or os.path.islink(path):
                os.unlink(path)
                removed.append(os.path.basename(path))
        except OSError:
            logger.debug('Не удалось удалить %r (возможно, активный Chrome)', path)
    if removed:
        logger.info('Очищены stale-блокировки профиля Chrome: %s', ', '.join(removed))


def _dns_page_blocked(title: str, src_head: str) -> bool:
    t = (title or '').strip()
    s = (src_head or '')[:12000]
    low = (t + '\n' + s).lower()
    if '403' in t or '403 error' in low[:800]:
        return True
    if 'forbidden' in t.lower() or 'http 403' in low:
        return True
    if 'доступ к сайту' in low and 'запрещ' in low:
        return True
    return False


def _parse_proxy_url(proxy: str) -> dict[str, Any]:
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
    manifest = (
        '{"version":"1.0.0","manifest_version":2,'
        '"name":"ProxyAuth","permissions":["proxy","tabs","unlimitedStorage",'
        '"storage","<all_urls>","webRequest","webRequestBlocking"],'
        '"background":{"scripts":["background.js"]},'
        '"minimum_chrome_version":"22.0.0"}'
    )
    background = (
        'var config = {\n'
        '  mode: "fixed_servers",\n'
        '  rules: {\n'
        f'    singleProxy: {{scheme: "{scheme}", host: "{host}", port: {port}}},\n'
        '    bypassList: ["localhost","127.0.0.1"]\n'
        '  }\n'
        '};\n'
        'chrome.proxy.settings.set({value: config, scope: "regular"}, function(){});\n'
        'chrome.webRequest.onAuthRequired.addListener(\n'
        '  function(details) {\n'
        f'    return {{authCredentials: {{username: "{username}", password: "{password}"}}}};\n'
        '  },\n'
        '  {urls: ["<all_urls>"]},\n'
        "  ['blocking']\n"
        ');\n'
    )
    ext_dir = tempfile.mkdtemp(prefix='proxy_auth_')
    zip_path = os.path.join(ext_dir, 'proxy_auth.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', manifest)
        zf.writestr('background.js', background)
    return zip_path


def _noop_chrome_quit(*_a: Any, **_k: Any) -> None:
    return None


class ChromeDriverMixin:

    headless: bool
    proxy: str | None
    max_retries: int
    delay_min: float
    delay_max: float
    page_load_timeout: int
    selenium_http_timeout: int
    start_minimized: bool
    user_data_dir: str
    _driver: Any
    _uc: Any
    _by: Any
    _ec: Any
    _web_driver_wait: Any
    _selenium_exceptions: Any
    _proxy_ext_dir: str | None

    def _init_chrome_runtime(
        self,
        *,
        page_timeout_setting: str,
        page_timeout_default: int,
        headless_setting: str | None = None,
        headless_default: bool | None = None,
        user_data_dir_setting: str | None = None,
    ) -> None:
        default_headless = getattr(settings, 'CHROME_HEADLESS', True)
        if headless_setting is not None:
            fallback = headless_default if headless_default is not None else default_headless
            self.headless = bool(getattr(settings, headless_setting, fallback))
        else:
            self.headless = bool(default_headless if headless_default is None else headless_default)

        self.delay_min = float(getattr(settings, 'PARSE_DELAY_MIN', 1.0))
        self.delay_max = float(getattr(settings, 'PARSE_DELAY_MAX', 3.0))
        self.max_retries = int(getattr(settings, 'PARSE_MAX_RETRIES', 3))
        self.page_load_timeout = int(getattr(settings, page_timeout_setting, page_timeout_default))
        self.selenium_http_timeout = int(getattr(settings, 'DNS_SELENIUM_HTTP_TIMEOUT', 300))

        self.start_minimized = (
            not self.headless
            and bool(getattr(settings, 'CHROME_START_MINIMIZED', True))
        )

        self.user_data_dir = ''
        if user_data_dir_setting:
            udd = getattr(settings, user_data_dir_setting, '') or ''
            self.user_data_dir = str(udd).strip()

        self._driver = None
        self._uc = None
        self._by = None
        self._ec = None
        self._web_driver_wait = None
        self._selenium_exceptions = None
        self._proxy_ext_dir = None

        self._load_selenium_deps()
        proxy_list: list[str] = getattr(settings, 'PROXY_LIST', [])
        self.proxy = random.choice(proxy_list) if proxy_list else None

    def _load_selenium_deps(self) -> None:
        try:
            self._uc = importlib.import_module('undetected_chromedriver')
            self._by = importlib.import_module('selenium.webdriver.common.by').By
            self._ec = importlib.import_module('selenium.webdriver.support.expected_conditions')
            self._web_driver_wait = importlib.import_module('selenium.webdriver.support.ui').WebDriverWait
            self._selenium_exceptions = importlib.import_module('selenium.common.exceptions')
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                'Missing parser dependency. Install selenium and undetected-chromedriver.'
            ) from exc

    def _build_options(self) -> Any:
        options = self._uc.ChromeOptions()
        try:
            options.page_load_strategy = 'eager'
        except Exception:
            pass
        for arg in (
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1920,1080',
            f'--user-agent={_chrome_user_agent()}',
            # Запрещаем Chrome снижать активность рендерера когда окно
            # не в фокусе, свёрнуто или за пределами экрана.
            # Без этих флагов Intersection Observer срабатывает редко,
            # JS-таймеры тормозят, lazy-load страниц не работает.
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-features=OptimizeBackground',
        ):
            options.add_argument(arg)

        if self.user_data_dir:
            try:
                os.makedirs(self.user_data_dir, exist_ok=True)
                _clean_stale_profile_locks(self.user_data_dir)
                options.add_argument(f'--user-data-dir={self.user_data_dir}')
                logger.info('Chrome профиль: %s', self.user_data_dir)
            except OSError:
                logger.warning(
                    'Не удалось создать user-data-dir=%r, Chrome запустится с temp-профилем',
                    self.user_data_dir,
                )

        self._attach_proxy(options)
        return options

    def _attach_proxy(self, options: Any) -> None:
        self._proxy_ext_dir = None
        if not self.proxy:
            return
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

    def _build_driver(self) -> Any:
        options = self._build_options()
        use_xvfb = self.headless and bool(os.environ.get('DISPLAY'))
        use_headless = self.headless and not use_xvfb

        ver_main = _chrome_major_version()
        uc_kwargs: dict[str, Any] = {'options': options, 'headless': use_headless}
        if ver_main is not None:
            uc_kwargs['version_main'] = ver_main
            logger.info('undetected_chromedriver version_main=%s', ver_main)

        # Принудительно указываем путь к Google Chrome.
        # Без этого undetected_chromedriver может подхватить /usr/bin/chromium-browser
        # (это snap-wrapper, который ломает парсинг даже если snap-chromium удалён).
        chrome_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/opt/google/chrome/google-chrome',
        ]
        for path in chrome_paths:
            if os.path.exists(path):
                uc_kwargs['browser_executable_path'] = path
                logger.info('Chrome binary: %s', path)
                break
        if use_xvfb:
            logger.info(
                'Xvfb-режим: Chrome запущен на виртуальном дисплее %s',
                os.environ['DISPLAY'],
            )
        elif use_headless:
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            logger.info('Headless-режим (без Xvfb)')

        driver = self._start_chrome_with_timeout(uc_kwargs)
        to = float(self.page_load_timeout)
        driver.set_page_load_timeout(to)
        try:
            driver.set_script_timeout(to)
        except Exception:
            pass
        self._apply_driver_http_timeout(driver)

        if self.start_minimized:
            try:
                # Перемещаем окно за пределы экрана вместо minimize_window().
                # minimize_window() вызывает throttling JS-движка и отключает
                # intersection observers, из-за чего lazy-load и «Показать ещё»
                # не работают. При off-screen позиции Chrome считает окно видимым
                # и рендерит страницу в полную силу — парсинг работает корректно.
                driver.set_window_position(-32000, 0)
                logger.info('Окно Chrome скрыто (off-screen, -32000,0)')
            except Exception:
                logger.debug('Не удалось скрыть окно Chrome off-screen', exc_info=True)

        return driver

    def _start_chrome_with_timeout(self, uc_kwargs: dict[str, Any]) -> Any:
        startup_timeout = int(getattr(settings, 'CHROME_STARTUP_TIMEOUT', 90))
        result: dict[str, Any] = {}

        def _target() -> None:
            try:
                result['driver'] = self._uc.Chrome(**uc_kwargs)
            except BaseException as exc:
                result['error'] = exc

        th = threading.Thread(target=_target, name='uc-chrome-startup', daemon=True)
        th.start()
        th.join(timeout=startup_timeout)

        if th.is_alive():
            raise RuntimeError(
                f'Chrome не стартовал за {startup_timeout}с. '
                f'Обычно это значит, что предыдущий Chrome жив и держит профиль '
                f'{self.user_data_dir!r}. Закройте все Chrome/chromedriver, '
                f'удалите Singleton* из профиля и повторите.'
            )
        if 'error' in result:
            raise result['error']
        driver = result.get('driver')
        if driver is None:
            raise RuntimeError('Chrome стартовал, но драйвер не был получен')
        return driver

    def _apply_driver_http_timeout(self, driver: Any) -> None:
        try:
            cfg = getattr(driver.command_executor, '_client_config', None)
            if cfg is not None:
                cfg.timeout = float(self.selenium_http_timeout)
        except Exception:
            logger.debug('Не удалось задать HTTP-таймаут клиента WebDriver', exc_info=True)

    def _driver_get(self, driver: Any, url: str) -> None:
        te = self._selenium_exceptions
        try:
            driver.get(url)
        except te.TimeoutException:
            logger.warning(
                'Таймаут загрузки страницы Chrome (%ss), останавливаем загрузку: %s',
                self.page_load_timeout, url,
            )
            try:
                driver.execute_script('window.stop();')
            except Exception:
                pass
        except te.WebDriverException as exc:
            err = str(exc).lower()
            if 'err_connection_timed_out' in err or 'err_connection_reset' in err:
                logger.error('Таймаут соединения: %s', url)
            elif 'err_proxy' in err or ('proxy' in err and 'failed' in err):
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
        if self._proxy_ext_dir:
            try:
                shutil.rmtree(self._proxy_ext_dir, ignore_errors=True)
            except Exception:
                pass
            self._proxy_ext_dir = None

    def _random_delay(self) -> None:
        time.sleep(random.uniform(self.delay_min, self.delay_max))


class DNSParser(ChromeDriverMixin, BaseParser):

    def __init__(self) -> None:
        self._init_chrome_runtime(
            page_timeout_setting='DNS_PAGE_LOAD_TIMEOUT',
            page_timeout_default=60,
            user_data_dir_setting='DNS_USER_DATA_DIR',
        )
        self.catalog_element_wait = int(getattr(settings, 'DNS_CATALOG_ELEMENT_WAIT', 60))
        self.catalog_scroll_max_rounds = int(
            getattr(settings, 'DNS_CATALOG_SCROLL_MAX_ROUNDS', 60),
        )
        self.catalog_scroll_stable = int(getattr(settings, 'DNS_CATALOG_SCROLL_STABLE', 5))
        self.catalog_scroll_min_rounds = int(
            getattr(settings, 'DNS_CATALOG_SCROLL_MIN_ROUNDS', 8),
        )
        self.catalog_scroll_pause = (
            float(getattr(settings, 'DNS_CATALOG_SCROLL_PAUSE_MIN', 2.0)),
            float(getattr(settings, 'DNS_CATALOG_SCROLL_PAUSE_MAX', 4.0)),
        )
        self.catalog_scroll_pause_short = (
            float(getattr(settings, 'DNS_CATALOG_SCROLL_PAUSE_SHORT_MIN', 1.2)),
            float(getattr(settings, 'DNS_CATALOG_SCROLL_PAUSE_SHORT_MAX', 2.4)),
        )
        self.catalog_scroll_pause_more = (
            float(getattr(settings, 'DNS_CATALOG_SCROLL_PAUSE_MORE_MIN', 2.5)),
            float(getattr(settings, 'DNS_CATALOG_SCROLL_PAUSE_MORE_MAX', 4.5)),
        )

    def _get_driver(self) -> Any:  # type: ignore[override]
        # Расширяем базовый _get_driver: после первого создания драйвера
        # инжектим скрипт «всегда видим/в фокусе» через CDP. Делает это
        # один раз на сессию — далее скрипт автоматически применяется к
        # каждой новой странице (включая редиректы и iframe).
        is_new = self._driver is None
        driver = super()._get_driver()
        if is_new:
            if getattr(settings, 'DNS_STEALTH', True):
                self._apply_stealth(driver)
            self._inject_saved_cookies(driver)
            try:
                driver.execute_cdp_cmd(
                    'Page.addScriptToEvaluateOnNewDocument',
                    {'source': _DNS_FORCE_FOREGROUND_JS},
                )
                logger.info(
                    'DNS: инжектирован visibility-override (off-screen окно '
                    'будет считаться видимым со стороны JS DNS).'
                )
            except Exception:
                logger.warning(
                    'DNS: не удалось добавить visibility-override через CDP. '
                    'Парсинг при свёрнутом окне может вернуть карточки без цен.',
                    exc_info=True,
                )
        return driver

    def _apply_stealth(self, driver: Any) -> None:
        # Анти-детект для Qrator: маскируем признаки автоматизации/Xvfb и
        # выставляем русскоязычные HTTP-заголовки. Best-effort — ошибки CDP
        # не должны ронять парсинг.
        try:
            driver.execute_cdp_cmd(
                'Page.addScriptToEvaluateOnNewDocument',
                {'source': _DNS_STEALTH_JS},
            )
            logger.info('DNS: инжектирован stealth-слой (анти-детект Qrator).')
        except Exception:
            logger.warning('DNS: не удалось добавить stealth-слой через CDP.', exc_info=True)
        try:
            driver.execute_cdp_cmd('Network.enable', {})
            driver.execute_cdp_cmd(
                'Network.setExtraHTTPHeaders',
                {'headers': {'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'}},
            )
        except Exception:
            logger.debug('DNS: не удалось задать Accept-Language через CDP', exc_info=True)

    def _inject_saved_cookies(self, driver: Any) -> None:
        # Инжектим clearance-куки Qrator из реального браузера (см.
        # scripts/export_dns_cookies.py) через CDP ДО навигации, чтобы первый
        # же запрос к DNS нёс валидную сессию и не упирался в 403.
        path = getattr(settings, 'DNS_COOKIES_FILE', '') or ''
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, encoding='utf-8') as f:
                cookies = json.load(f)
        except Exception:
            logger.warning('DNS: не удалось прочитать cookies-файл %r', path, exc_info=True)
            return
        if not isinstance(cookies, list) or not cookies:
            return
        try:
            driver.execute_cdp_cmd('Network.enable', {})
        except Exception:
            pass
        injected = 0
        qrator = 0
        for c in cookies:
            name = c.get('name')
            if not name:
                continue
            domain = (c.get('domain') or '').lstrip('.')
            if not domain:
                continue
            params: dict[str, Any] = {
                'name': name,
                'value': c.get('value', ''),
                'domain': c.get('domain'),
                'path': c.get('path') or '/',
                'secure': bool(c.get('secure', True)),
                'httpOnly': bool(c.get('httpOnly', False)),
            }
            if c.get('expires'):
                params['expires'] = float(c['expires'])
            if c.get('sameSite') in ('Strict', 'Lax', 'None'):
                params['sameSite'] = c['sameSite']
            try:
                driver.execute_cdp_cmd('Network.setCookie', params)
                injected += 1
                if 'qrator' in name.lower():
                    qrator += 1
            except Exception:
                logger.debug('DNS: не удалось установить cookie %s', name, exc_info=True)
        logger.info(
            'DNS: инжектировано %d cookies из реального браузера (qrator clearance: %d).',
            injected, qrator,
        )

    def _wait_for_prices(
        self,
        driver: Any,
        *,
        min_priced: int = 6,
        timeout: float = 25.0,
        poll: float = 0.6,
    ) -> tuple[int, int]:
        """Ждёт, пока на странице появятся цены у достаточного числа карточек.

        DNS подгружает цены асинхронно после первого user-events / появления
        в области просмотра. Без этой паузы парсер видит карточки, но цены
        ещё не отрисованы, и извлечение возвращает 0.
        """
        deadline = time.time() + max(1.0, timeout)
        last: tuple[int, int] = (0, 0)
        while time.time() < deadline:
            try:
                info = driver.execute_script(_DNS_PRICE_READY_JS) or {}
                cards = int(info.get('cards') or 0)
                priced = int(info.get('priced') or 0)
            except Exception:
                cards, priced = 0, 0
            last = (cards, priced)
            if cards > 0 and priced >= min(min_priced, cards):
                return last
            # Будим страницу: каждый тик имитируем активность и микро-скролл.
            try:
                driver.execute_script(_DNS_NUDGE_ACTIVITY_JS)
            except Exception:
                pass
            try:
                driver.execute_script(
                    'window.scrollBy({top: arguments[0], behavior: "instant"});',
                    120 if int(time.time()) % 2 == 0 else -120,
                )
            except Exception:
                pass
            time.sleep(poll)
        return last

    def _check_dns_blocked(self, driver: Any) -> None:
        te = self._selenium_exceptions
        title = ''
        src = ''
        try:
            title = (driver.title or '').strip()
            ps = driver.page_source
            if ps:
                src = ps[:12000]
        except (te.NoSuchWindowException, te.InvalidSessionIdException):
            logger.warning('Chrome: окно или сессия недоступны')
            raise
        except Exception:
            pass
        if _dns_page_blocked(title, src):
            raise DNSBlockedError(DNS_BLOCKED_MSG)

    def _navigate_dns_with_warmup(self, driver: Any, url: str) -> None:
        try:
            cur = driver.current_url or ''
        except Exception:
            cur = ''
        if 'dns-shop.ru' not in cur:
            try:
                self._driver_get(driver, f'{DNS_BASE_URL}/')
                time.sleep(random.uniform(2.0, 4.5))
            except Exception:
                logger.debug('Предварительный заход на главную DNS не удался', exc_info=True)
        self._driver_get(driver, url)
        time.sleep(2)
        self._check_dns_blocked(driver)
        # Сразу после загрузки имитируем активность — это будит JS DNS
        # и запускает первичную загрузку цен.
        try:
            driver.execute_script(_DNS_NUDGE_ACTIVITY_JS)
        except Exception:
            pass

    def parse_category(self, category_url: str) -> list[ParsedProduct]:
        cu = (category_url or '').strip()
        if cu.startswith('http'):
            url = cu
        else:
            url = f'{DNS_BASE_URL}/catalog/{cu.strip("/")}/'
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
                        backoff += random.uniform(20.0, 45.0)
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
                    self.catalog_element_wait, driver.current_url, driver.title,
                )
            except Exception:
                pass
            raise
        self._random_delay()
        self._scroll_to_load_all(driver)

        product_elements = driver.find_elements(self._by.CLASS_NAME, 'catalog-product')
        logger.info('Найдено элементов на странице: %d', len(product_elements))

        # Перед извлечением убеждаемся, что цены уже отрисованы.
        # При off-screen / свёрнутом окне DNS подгружает цены лениво,
        # и без этой паузы получаем карточки без price-элементов.
        prices_timeout = float(getattr(settings, 'DNS_PRICES_WAIT_TIMEOUT', 30.0))
        cards_seen, priced = self._wait_for_prices(
            driver,
            min_priced=max(1, min(8, len(product_elements))),
            timeout=prices_timeout,
        )
        if cards_seen and priced < cards_seen:
            logger.info(
                'DNS: цены подгружены у %d / %d карточек (timeout=%.0fs).',
                priced, cards_seen, prices_timeout,
            )
        if cards_seen and priced == 0:
            logger.warning(
                'DNS: за %.0fs ни у одной из %d карточек не появилась цена. '
                'Похоже, страница «не активна» с точки зрения JS DNS '
                '(visibility/focus override не сработал). Извлечение всё равно '
                'попытаемся, но скорее всего вернёт 0 товаров.',
                prices_timeout, cards_seen,
            )

        rows = self._extract_rows_via_js(driver)
        if rows:
            products = self._rows_to_parsed(rows)
            logger.info('Карточки разобраны пакетом в браузере (JS), записей: %d', len(rows))
        else:
            products = self._extract_via_dom(product_elements)

        if product_elements and not products:
            try:
                sample = (product_elements[0].text or '').strip().replace('\n', ' ')
                sample = re.sub(r'\s+', ' ', sample)[:220]
            except Exception:
                sample = ''
            logger.warning(
                'Найдено %d карточек .catalog-product, но извлечь товары не удалось. '
                'Возможно, изменилась вёрстка. Текст первой карточки: %r',
                len(product_elements), sample,
            )
        return products

    def _extract_rows_via_js(self, driver: Any) -> list[dict[str, Any]]:
        try:
            raw = driver.execute_script(_DNS_CATALOG_CARDS_EXTRACT_JS)
        except Exception:
            logger.warning('Пакетное извлечение DNS-карточек (JS) не удалось', exc_info=True)
            return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    @staticmethod
    def _rows_to_parsed(rows: list[dict[str, Any]]) -> list[ParsedProduct]:
        seen: dict[str, ParsedProduct] = {}
        for row in rows:
            url = (row.get('url') or '').strip()
            name = (row.get('name') or '').strip()
            if not url or not name:
                continue
            try:
                price = int(row['price']) if row.get('price') is not None else None
            except (TypeError, ValueError):
                price = None
            if price is None:
                continue
            op = row.get('old_price')
            try:
                old_price: int | None = int(op) if op is not None else None
            except (TypeError, ValueError):
                old_price = None
            if url in seen:
                continue
            seen[url] = ParsedProduct(
                name=name,
                price=price,
                url=url,
                vendor_code=str(row.get('vendor_code') or ''),
                image_url=str(row.get('image_url') or ''),
                old_price=old_price,
                is_available=bool(row.get('is_available', True)),
            )
        return list(seen.values())

    def _extract_via_dom(self, product_elements: list[Any]) -> list[ParsedProduct]:
        seen: dict[str, ParsedProduct] = {}
        for el in product_elements:
            try:
                parsed = self._extract_product_from_element(el)
            except Exception:
                logger.debug('Не удалось извлечь товар из элемента', exc_info=True)
                continue
            if parsed and parsed.url not in seen:
                seen[parsed.url] = parsed
        return list(seen.values())

    def _click_catalog_more(self, driver: Any) -> bool:
        # Используем JS-проверку видимости вместо is_displayed(),
        # так как is_displayed() возвращает False при off-screen / minimized окне.
        _is_visible_js = (
            'var r = arguments[0].getBoundingClientRect();'
            'var s = window.getComputedStyle(arguments[0]);'
            'return s.display !== "none" && s.visibility !== "hidden"'
            ' && parseFloat(s.opacity) > 0 && !arguments[0].disabled;'
        )
        for sel in (
            'button.catalog-more__button',
            '.catalog-more__button',
            '[data-role="catalog-more"]',
            'button.catalog-category__more',
        ):
            try:
                el = driver.find_element(self._by.CSS_SELECTOR, sel)
                if driver.execute_script(_is_visible_js, el):
                    driver.execute_script('arguments[0].click();', el)
                    return True
            except Exception:
                pass
        for label in ('Показать ещё', 'Показать еще', 'Показать больше'):
            xp = (
                f"//button[contains(normalize-space(.), '{label}')]"
                f"|//a[contains(normalize-space(.), '{label}')]"
            )
            try:
                for el in driver.find_elements(self._by.XPATH, xp):
                    if driver.execute_script(_is_visible_js, el):
                        driver.execute_script('arguments[0].click();', el)
                        return True
            except Exception:
                pass
        return False

    # Инкрементальный скролл: двигаемся на один «экран» вниз.
    # window.scrollBy надёжнее scrollIntoView — он не перепрыгивает
    # через IO-триггер (элемент, на котором DNS вешает «подгрузить ещё»).
    # Дополнительно диспатчим WheelEvent для эмуляции живого пользователя.
    _SCROLL_STEP_JS = r"""
    var step = arguments[0] || 700;
    var prevY = window.pageYOffset;
    window.scrollBy({ top: step, behavior: 'instant' });
    try {
        window.dispatchEvent(new WheelEvent('wheel', { deltaY: step, bubbles: true }));
    } catch(e) {}
    try { window.dispatchEvent(new Event('scroll')); } catch(e) {}
    return {
        prevY: prevY,
        curY: window.pageYOffset,
        maxY: Math.max(0, document.documentElement.scrollHeight
                          - document.documentElement.clientHeight),
        count: document.querySelectorAll('.catalog-product').length
    };
    """

    # После окончания инкрементального скролла прокручиваем до самого низа.
    _SCROLL_BOTTOM_JS = r"""
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' });
    try { window.dispatchEvent(new Event('scroll')); } catch(e) {}
    return document.querySelectorAll('.catalog-product').length;
    """

    # Считываем счётчик «Показано N из M товаров» со страницы DNS.
    # Возвращает {shown: N, total: M} или null если счётчик не найден.
    _READ_COUNTER_JS = r"""
    (function() {
        // DNS показывает что-то вроде "Показано 36 из 120 товаров"
        var selectors = [
            '.products-count__count',
            '.products-count',
            '[class*="products-count"]',
            '.catalog-products__info',
            '[class*="catalog-count"]',
            '.catalog-result__count',
        ];
        function parseTwo(text) {
            var nums = (text || '').match(/\d+/g);
            if (nums && nums.length >= 2) {
                return { shown: parseInt(nums[0]), total: parseInt(nums[nums.length - 1]) };
            }
            return null;
        }
        for (var i = 0; i < selectors.length; i++) {
            var el = document.querySelector(selectors[i]);
            if (el) {
                var res = parseTwo(el.textContent || '');
                if (res && res.total > 0) return res;
            }
        }
        // Fallback: ищем текст «из N» во всём документе
        var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        var node;
        while ((node = walker.nextNode())) {
            var t = node.textContent || '';
            if (t.indexOf('из') !== -1 && t.indexOf('товар') !== -1) {
                var res2 = parseTwo(t);
                if (res2 && res2.total > 0) return res2;
            }
        }
        return null;
    })();
    """

    def _read_dns_counter(self, driver: Any) -> tuple[int, int] | None:
        """Возвращает (shown, total) из счётчика DNS или None если не найдено."""
        try:
            result = driver.execute_script(self._READ_COUNTER_JS)
            if isinstance(result, dict):
                shown = int(result.get('shown') or 0)
                total = int(result.get('total') or 0)
                if total > 0:
                    return shown, total
        except Exception:
            pass
        return None

    def _scroll_to_load_all(self, driver: Any) -> None:
        """Прокручивает каталог DNS инкрементально, давая IO-триггерам срабатывать."""
        max_r = max(1, self.catalog_scroll_max_rounds)
        need_stable = max(1, self.catalog_scroll_stable)
        min_rounds = max(1, self.catalog_scroll_min_rounds)

        # Размер шага — ~70% высоты вьюпорта, чтобы не перескакивать IO-триггер
        try:
            viewport_h = driver.execute_script(
                'return document.documentElement.clientHeight || 900;'
            )
            step = max(400, int(float(viewport_h) * 0.7))
        except Exception:
            step = 700

        stable = 0
        prev_count = len(driver.find_elements(self._by.CLASS_NAME, 'catalog-product'))
        at_bottom_rounds = 0

        # Читаем ожидаемое количество товаров со страницы (ранний выход)
        expected_total: int | None = None
        counter = self._read_dns_counter(driver)
        if counter:
            expected_total = counter[1]
            logger.info('DNS каталог: ожидается %s товаров (по счётчику страницы)', expected_total)

        for rnd in range(max_r):
            # Ранний выход: уже загрузили все товары по счётчику страницы
            if expected_total and prev_count >= expected_total:
                logger.info(
                    'Все товары загружены: %s/%s (раунд %s).',
                    prev_count, expected_total, rnd + 1,
                )
                return

            # Шаг скролла вниз
            try:
                info = driver.execute_script(self._SCROLL_STEP_JS, step)
            except Exception:
                logger.debug('DNS scroll step JS failed', exc_info=True)
                info = {}

            at_bottom = isinstance(info, dict) and info.get('curY', 0) >= info.get('maxY', 1) - 5
            pause_range = (
                self.catalog_scroll_pause_short
                if not at_bottom
                else self.catalog_scroll_pause
            )
            time.sleep(random.uniform(*pause_range))

            # Если добрались до низа — попробуем «Показать ещё» и финальный scroll
            if at_bottom:
                at_bottom_rounds += 1
                clicked = self._click_catalog_more(driver)
                if clicked:
                    stable = 0
                    at_bottom_rounds = 0
                    time.sleep(random.uniform(*self.catalog_scroll_pause_more))
                    # После подгрузки отматываем немного назад, чтобы IO сработал
                    try:
                        driver.execute_script(
                            'window.scrollBy({ top: -300, behavior: "instant" });'
                        )
                    except Exception:
                        pass
                    time.sleep(random.uniform(0.4, 0.8))
                    continue

                # Последний шанс: прокрутка к самому низу
                try:
                    driver.execute_script(self._SCROLL_BOTTOM_JS)
                    time.sleep(random.uniform(*self.catalog_scroll_pause_short))
                except Exception:
                    pass

            cur_count = len(driver.find_elements(self._by.CLASS_NAME, 'catalog-product'))
            if cur_count > prev_count:
                logger.debug('Каталог DNS: +%s карточек (всего %s)', cur_count - prev_count, cur_count)
                stable = 0
                at_bottom_rounds = 0
                prev_count = cur_count
                # Обновим expected_total если счётчик изменился
                if not expected_total:
                    counter = self._read_dns_counter(driver)
                    if counter:
                        expected_total = counter[1]
                        logger.info(
                            'DNS каталог: обновлён ожидаемый итог — %s товаров',
                            expected_total,
                        )
                continue

            stable += 1
            if stable >= need_stable and (rnd + 1) >= min_rounds:
                logger.info(
                    'Подгрузка каталога завершена: карточек в DOM %s '
                    '(%s раундов без роста подряд, раунд %s).',
                    cur_count, need_stable, rnd + 1,
                )
                return

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
                    time.sleep(2 ** attempt + random.uniform(0, 1))

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

        price = self._extract_price_class(driver, 'product-buy__price')
        if price is None:
            return None

        old_price = self._extract_price_class(driver, 'product-buy__prev')

        vendor_code = ''
        try:
            vc_text = driver.find_element(self._by.CLASS_NAME, 'product-card-top__code').text.strip()
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
            price = self._extract_price_class(el, cls)
            if price is not None:
                break
        if price is None:
            for c in el.find_elements(self._by.XPATH, ".//*[contains(text(),'₽')]"):
                price = self._clean_price(c.text or c.get_attribute('textContent') or '')
                if price is not None:
                    break
        if price is None:
            return None

        old_price = None
        for cls in ('product-buy__prev', 'catalog-product__old-price', 'ui-kit-price__old'):
            old_price = self._extract_price_class(el, cls)
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

        try:
            card_text_low = (el.text or '')[:4000].lower()
        except Exception:
            card_text_low = ''
        is_available = (
            'нет в наличии' not in card_text_low
            and 'снят с производства' not in card_text_low
        )
        return ParsedProduct(
            name=name,
            price=price,
            url=link,
            vendor_code=vendor_code,
            image_url=image_url,
            old_price=old_price,
            is_available=is_available,
        )

    @staticmethod
    def _find_first_element(parent: Any, selectors: tuple[tuple[Any, str], ...]) -> Any | None:
        for by, sel in selectors:
            try:
                return parent.find_element(by, sel)
            except Exception:
                continue
        return None

    def _extract_price_class(self, parent: Any, class_name: str) -> int | None:
        try:
            el = parent.find_element(self._by.CLASS_NAME, class_name)
            return self._clean_price(el.get_attribute('textContent'))
        except Exception:
            return None

    @staticmethod
    def _clean_price(raw: str) -> int | None:
        cleaned = (raw or '').split('₽')[0]
        cleaned = re.sub(r'\s+', '', cleaned)
        cleaned = re.sub(r'[^\d]', '', cleaned)
        return int(cleaned) if cleaned.isdigit() else None

    def _safe_text(self, driver: Any, class_name: str) -> str:
        try:
            el = driver.find_element(self._by.CLASS_NAME, class_name)
            return el.text.strip()
        except Exception:
            return ''
