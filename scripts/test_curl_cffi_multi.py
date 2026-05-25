#!/usr/bin/env python
"""Перебор impersonate-вариантов для curl-cffi против DNS-shop.

Пытается разные TLS-fingerprint'ы (Chrome версии, Safari, Firefox)
и показывает какие проходят Qrator.
"""
import os
import random
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings  # noqa: E402

from curl_cffi import requests  # noqa: E402


IMPERSONATES = [
    'chrome131',
    'chrome124',
    'chrome120',
    'chrome116',
    'chrome110',
    'safari17_0',
    'safari17_2_ios',
    'edge101',
    'firefox133',
]


def main(url: str) -> None:
    proxy_list = getattr(settings, 'PROXY_LIST', [])
    proxy = random.choice(proxy_list) if proxy_list else None
    proxies = {'http': proxy, 'https': proxy} if proxy else None

    print(f'URL: {url}')
    print(f'Proxy: {proxy or "(нет)"}')
    print()
    print(f'{"impersonate":20} | {"HTTP":>5} | {"Размер":>8} | catalog-product | qrator | Заметки')
    print('-' * 110)

    for imp in IMPERSONATES:
        try:
            r = requests.get(url, impersonate=imp, proxies=proxies, timeout=30)
            html = r.text.lower()
            has_cards = 'catalog-product' in html
            has_qrator = 'qrator' in html or r.headers.get('server', '').lower() == 'qrator'
            note = ''
            if r.status_code == 200 and has_cards:
                note = '🎉 SUCCESS'
            elif r.status_code == 200 and not has_cards:
                note = 'SPA-каркас?'
            elif r.status_code == 403:
                note = '❌ блок'
            elif r.status_code == 401:
                note = '❌ challenge'
            else:
                note = f'? {r.status_code}'

            print(f'{imp:20} | {r.status_code:>5} | {len(r.text):>8} | '
                  f'{"✓" if has_cards else "✗":>15} | '
                  f'{"✓" if has_qrator else "✗":>6} | {note}')
        except Exception as exc:
            print(f'{imp:20} | ERROR: {exc}')


if __name__ == '__main__':
    default_url = 'https://www.dns-shop.ru/catalog/17a89a3916404e77/operativnaya-pamyat/'
    url = sys.argv[1] if len(sys.argv) > 1 else default_url
    main(url)
