#!/usr/bin/env python
"""Attach к уже работающему Chrome через CDP.

Алгоритм:
1. Запусти Chrome вручную с remote-debugging-port:
     google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_parser

2. В этом Chrome вручную зайди на dns-shop.ru (пройди Qrator challenge один раз)
3. Запусти этот скрипт — он подключится к ТВОЕМУ Chrome и спарсит каталог.

Этот подход работает потому что Qrator видит реальный браузер пользователя
со всеми его cookies, JS-историей, fingerprint'ом — а не Selenium-инстанс.
"""
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def main(url: str) -> None:
    print(f'Подключаюсь к Chrome на 127.0.0.1:9222...')
    options = Options()
    options.add_experimental_option('debuggerAddress', '127.0.0.1:9222')

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:
        print('❌ Не удалось подключиться.')
        print('Убедись что Chrome запущен с флагом:')
        print('   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_parser')
        print(f'\nОшибка: {exc}')
        sys.exit(1)

    print(f'✓ Подключен. Текущая вкладка: {driver.current_url}')
    print(f'  Title: {driver.title}')

    print(f'\nПерехожу на {url}...')
    driver.get(url)
    time.sleep(8)

    out_dir = Path('/tmp/dns_debug')
    out_dir.mkdir(exist_ok=True)

    html = driver.page_source
    title = driver.title
    cur_url = driver.current_url

    screenshot = out_dir / 'attached.png'
    html_path = out_dir / 'attached.html'

    driver.save_screenshot(str(screenshot))
    html_path.write_text(html, encoding='utf-8')

    print()
    print(f'  Title:       {title!r}')
    print(f'  Current URL: {cur_url}')
    print(f'  HTML size:   {len(html)} bytes')

    markers = {
        '403/доступ запрещён': '403' in title or 'access denied' in html.lower(),
        'qrator challenge': '__qrator' in html.lower(),
        'каталог карточек (catalog-product)': 'catalog-product' in html.lower(),
        'real catalog (product-name)': 'catalog-product__name' in html.lower(),
    }
    print('\nДетекторы:')
    for name, found in markers.items():
        print(f'  {"✓" if found else "✗"} {name}')

    if 'catalog-product' in html.lower() and '403' not in title:
        print('\n🎉 SUCCESS! DNS каталог доступен через attached Chrome!')
        print('Можно делать парсер на этом принципе.')
    elif '403' in title:
        print('\n⚠ DNS вернул 403 даже в твоём Chrome.')
        print('Зайди в Chrome руками на dns-shop.ru, пройди challenge, потом повтори.')
    else:
        print('\n⚠ Странный результат — посмотри HTML и скриншот.')

    print(f'\n📷 Скриншот: {screenshot}')
    print(f'📄 HTML:     {html_path}')
    print('\nChrome остаётся открытым (driver.quit() не вызываем) — используй его дальше.')


if __name__ == '__main__':
    default = 'https://www.dns-shop.ru/catalog/17a89a3916404e77/operativnaya-pamyat/'
    main(sys.argv[1] if len(sys.argv) > 1 else default)
