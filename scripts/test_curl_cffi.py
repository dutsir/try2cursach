#!/usr/bin/env python
"""Тест: проходит ли curl-cffi (с импер­сонацией Chrome TLS) через Qrator на DNS.

Если этот скрипт получает HTTP 200 и видит карточки товаров — стратегия с
curl-cffi сработает, переписываем DNS-парсер.
"""
import os
import random
import sys
from pathlib import Path

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings  # noqa: E402

from curl_cffi import requests  # noqa: E402


def main(url: str) -> None:
    proxy_list = getattr(settings, 'PROXY_LIST', [])
    proxy = random.choice(proxy_list) if proxy_list else None

    proxies = None
    if proxy:
        # curl-cffi принимает прокси в формате http://user:pass@host:port
        proxies = {'http': proxy, 'https': proxy}

    print(f'URL: {url}')
    print(f'Proxy: {proxy or "(нет)"}')
    print()

    # Импер­сонируем Chrome 131 — последний поддерживаемый curl-cffi
    impersonate = 'chrome131'

    # Запрос
    try:
        r = requests.get(
            url,
            impersonate=impersonate,
            proxies=proxies,
            timeout=60,
        )
    except Exception as exc:
        print(f'❌ Ошибка запроса: {exc}')
        sys.exit(1)

    print(f'HTTP {r.status_code}')
    print(f'Размер: {len(r.text)} байт')
    print(f'Server: {r.headers.get("server", "(none)")}')
    print()

    # Анализ
    html = r.text.lower()
    markers = {
        'qrator (server)': r.headers.get('server', '').lower() == 'qrator',
        'qrator (HTML)': 'qrator' in html,
        '403/доступ запрещён': 'доступ запрещён' in html or 'access denied' in html,
        'captcha': 'captcha' in html or 'smartcaptcha' in html,
        'каталог карточек (catalog-product)': 'catalog-product' in html,
        'каталог-product__name (DNS-specific)': 'catalog-product__name' in html,
        'json-данные в HTML': 'window.__nuxt__' in html or '"products":' in html,
    }
    print('Детекторы:')
    for name, found in markers.items():
        print(f'  {"✓" if found else "✗"} {name}')

    # Сохраняем HTML
    out_dir = Path('/tmp/dns_debug')
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / 'curl_cffi.html'
    out_path.write_text(r.text, encoding='utf-8')
    print(f'\nHTML сохранён: {out_path}')

    if r.status_code == 200 and 'catalog-product' in html:
        print()
        print('🎉 SUCCESS! DNS открывается через curl-cffi и карточки есть в HTML.')
        print('Можно переписывать парсер с Selenium на curl-cffi.')
    elif r.status_code == 200:
        print()
        print('⚠ DNS вернул 200, но карточек товаров не видно.')
        print('Возможно DNS отдал SPA-каркас без SSR. Нужно искать API endpoint.')
    elif r.status_code == 403:
        print()
        print('❌ DNS вернул 403. Qrator всё равно блокирует.')
        print('Попробуй: другой sticky session порт или impersonate=chrome120.')
    else:
        print()
        print(f'⚠ HTTP {r.status_code} — нужен анализ HTML.')


if __name__ == '__main__':
    default_url = 'https://www.dns-shop.ru/catalog/17a89a3916404e77/operativnaya-pamyat/'
    url = sys.argv[1] if len(sys.argv) > 1 else default_url
    main(url)
