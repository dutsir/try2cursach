#!/usr/bin/env python
"""Проверка: работает ли Chrome БЕЗ прокси.

Если Chrome работает без прокси, но падает с прокси → проблема в прокси.
Если падает и без прокси → проблема в Chrome/Xvfb/системе.
"""
import os
import time
from pathlib import Path

import undetected_chromedriver as uc


def main() -> None:
    out_dir = Path('/tmp/dns_debug')
    out_dir.mkdir(exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    use_xvfb = bool(os.environ.get('DISPLAY'))
    use_headless = not use_xvfb
    ver_main = int(os.environ.get('CHROME_VERSION_MAIN', '148'))

    print(f'Headless: {use_headless} (Xvfb: {use_xvfb})')
    print('Запускаю Chrome БЕЗ прокси...')

    driver = uc.Chrome(version_main=ver_main, options=options, headless=use_headless)
    driver.set_page_load_timeout(60)

    try:
        print('Открываю https://ipinfo.io/json ...')
        driver.get('https://ipinfo.io/json')
        time.sleep(5)

        html = driver.page_source
        driver.save_screenshot(str(out_dir / 'noproxy_ipinfo.png'))
        (out_dir / 'noproxy_ipinfo.html').write_text(html, encoding='utf-8')

        print(f'  Title: {driver.title!r}')
        print(f'  URL:   {driver.current_url}')
        print(f'  Size:  {len(html)} bytes')
        print(f'  HTML preview: {repr(html[:300])}')

    finally:
        driver.quit()


if __name__ == '__main__':
    main()
