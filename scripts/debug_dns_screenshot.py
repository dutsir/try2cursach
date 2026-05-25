#!/usr/bin/env python
"""Debug-скрипт: пошаговая проверка прокси + DNS через Chrome.

Логика:
1. Открываем ipinfo.io — проверяем что прокси работает в Chrome
2. Открываем главную DNS — warmup
3. Открываем каталог DNS — основной тест
4. На каждом шаге: скриншот + сохранение HTML + анализ

Запуск:
    source venv/bin/activate
    export DISPLAY=:99
    python scripts/debug_dns_screenshot.py

Результаты в /tmp/dns_debug/:
    01_ipinfo.png/html      — проверка прокси
    02_dns_home.png/html    — главная DNS
    03_dns_catalog.png/html — каталог DNS
    info.txt                — отчёт по всем шагам
"""
from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings  # noqa: E402

import undetected_chromedriver as uc  # noqa: E402


def take_step(driver, name: str, url: str, wait: int, out_dir: Path, lines: list) -> None:
    """Сходить на URL, подождать, сохранить скриншот + HTML."""
    print(f'\n=== {name}: {url} ===')
    try:
        driver.get(url)
    except Exception as exc:
        lines.append(f'\n{name}: НЕ ОТКРЫЛОСЬ — {exc}')
        print(f'  ❌ Ошибка: {exc}')
        return

    print(f'  Жду {wait} сек...')
    time.sleep(wait)

    png = out_dir / f'{name}.png'
    html_path = out_dir / f'{name}.html'

    try:
        driver.save_screenshot(str(png))
    except Exception as exc:
        print(f'  ⚠ Скриншот не получился: {exc}')

    try:
        html = driver.page_source
        html_path.write_text(html, encoding='utf-8')
        title = driver.title
        cur_url = driver.current_url
    except Exception as exc:
        html = ''
        title = '(no access)'
        cur_url = '(no access)'
        print(f'  ⚠ Не удалось прочитать страницу: {exc}')

    info = [
        f'\n{"=" * 60}',
        f'{name}',
        f'{"=" * 60}',
        f'  Requested URL:  {url}',
        f'  Current URL:    {cur_url}',
        f'  Page title:     {title}',
        f'  Page size:      {len(html)} bytes',
    ]
    markers = {
        'qrator': 'qrator' in html.lower(),
        'captcha': 'captcha' in html.lower(),
        'smartcaptcha': 'smartcaptcha' in html.lower(),
        'access denied / 403': 'access denied' in html.lower() or 'доступ запрещён' in html.lower() or '403' in title,
        'catalog-product': 'catalog-product' in html.lower(),
        'window.QRATOR (JS-challenge)': 'window.QRATOR' in html,
        'cloudflare challenge': 'cf-browser-verification' in html.lower(),
        'browser check': 'just a moment' in html.lower() or 'checking your browser' in html.lower(),
    }
    info.append('  Детекторы:')
    for marker_name, found in markers.items():
        info.append(f'    {"✓" if found else "✗"} {marker_name}')

    info.append(f'\n  HTML preview (первые 300 символов):')
    info.append(f'  {repr(html[:300])}')

    lines.extend(info)

    print(f'  Title: {title!r}')
    print(f'  Size:  {len(html)} bytes')
    for marker_name, found in markers.items():
        if found:
            print(f'    ⚠ Обнаружено: {marker_name}')


def main() -> None:
    out_dir = Path('/tmp/dns_debug')
    out_dir.mkdir(exist_ok=True)
    # Чистим старые артефакты
    for f in out_dir.glob('*'):
        try:
            f.unlink()
        except OSError:
            pass

    proxy_list = getattr(settings, 'PROXY_LIST', [])
    proxy = random.choice(proxy_list) if proxy_list else None

    print(f'Proxy: {proxy or "(без прокси)"}')
    print(f'DISPLAY: {os.environ.get("DISPLAY", "(нет)")}')

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    use_xvfb = bool(os.environ.get('DISPLAY'))
    use_headless = not use_xvfb

    if proxy:
        from urllib.parse import urlparse
        parsed = urlparse(proxy if '://' in proxy else f'http://{proxy}')
        host = parsed.hostname
        port = parsed.port
        options.add_argument(f'--proxy-server={host}:{port}')
        print(f'  → Chrome proxy: {host}:{port}')

    ver_main = int(os.environ.get('CHROME_VERSION_MAIN', '148'))
    print(f'  → Chrome version_main: {ver_main}')
    print(f'  → Headless: {use_headless} (Xvfb: {use_xvfb})')

    print('\nЗапускаю Chrome...')
    driver = uc.Chrome(version_main=ver_main, options=options, headless=use_headless)
    driver.set_page_load_timeout(60)

    lines: list[str] = [
        f'Proxy: {proxy}',
        f'DISPLAY: {os.environ.get("DISPLAY", "(нет)")}',
        f'Chrome version_main: {ver_main}',
        f'Headless: {use_headless}',
    ]

    try:
        # Шаг 1: ipinfo — проверка что прокси вообще работает в Chrome
        take_step(
            driver,
            name='01_ipinfo',
            url='https://ipinfo.io/json',
            wait=10,
            out_dir=out_dir,
            lines=lines,
        )

        # Шаг 2: главная DNS — warmup
        take_step(
            driver,
            name='02_dns_home',
            url='https://www.dns-shop.ru/',
            wait=20,
            out_dir=out_dir,
            lines=lines,
        )

        # Шаг 3: каталог DNS — основной тест
        catalog_url = (
            sys.argv[1]
            if len(sys.argv) > 1
            else 'https://www.dns-shop.ru/catalog/17a89a3916404e77/operativnaya-pamyat/'
        )
        take_step(
            driver,
            name='03_dns_catalog',
            url=catalog_url,
            wait=25,
            out_dir=out_dir,
            lines=lines,
        )

        info_path = out_dir / 'info.txt'
        info_path.write_text('\n'.join(lines), encoding='utf-8')

        print()
        print('=' * 60)
        print(f'ГОТОВО. Файлы в {out_dir}')
        print('=' * 60)
        print('Просмотр:')
        print(f'  eog {out_dir}/01_ipinfo.png   # IP info — должны быть видны JSON и RU IP')
        print(f'  eog {out_dir}/02_dns_home.png # Главная DNS')
        print(f'  eog {out_dir}/03_dns_catalog.png # Каталог')
        print(f'  cat {out_dir}/info.txt        # Текстовый отчёт')

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
