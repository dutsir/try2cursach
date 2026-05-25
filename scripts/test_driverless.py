#!/usr/bin/env python
"""Тест selenium-driverless — alternative к undetected_chromedriver.

selenium-driverless не использует Selenium WebDriver protocol — работает
напрямую через Chrome DevTools Protocol (CDP). Из-за этого:
- navigator.webdriver всегда false (нет вебдрайвера)
- меньше специфичных Chrome флагов
- лучше проходит anti-bot защиту вроде Qrator
"""
import asyncio
import os
import sys
from pathlib import Path


async def main(url: str) -> None:
    from selenium_driverless import webdriver
    from selenium_driverless.types.by import By  # noqa: F401

    out_dir = Path('/tmp/dns_debug')
    out_dir.mkdir(exist_ok=True)

    options = webdriver.ChromeOptions()
    # Запускаем в Xvfb (без видимого окна)
    if os.environ.get('DISPLAY'):
        print(f'Используем DISPLAY={os.environ["DISPLAY"]} (Xvfb)')
    else:
        options.headless = True

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    print('Запускаю Chrome через selenium-driverless...')
    async with webdriver.Chrome(options=options) as driver:
        print(f'Перехожу на {url}...')
        await driver.get(url, wait_load=True, timeout=60)

        # Подождём JS-challenge
        print('Жду 12 сек чтобы Qrator JS успел отработать...')
        await asyncio.sleep(12)

        title = await driver.title
        cur_url = driver.current_url
        html = await driver.source

        print()
        print(f'  Title:       {title!r}')
        print(f'  Current URL: {cur_url}')
        print(f'  HTML size:   {len(html)} bytes')

        await driver.get_screenshot_as_file(str(out_dir / 'driverless.png'))
        (out_dir / 'driverless.html').write_text(html, encoding='utf-8')

        markers = {
            '403/доступ запрещён': '403' in title or 'доступ запрещён' in html.lower(),
            'qrator challenge (__qrator)': '__qrator' in html.lower(),
            'каталог карточек (catalog-product)': 'catalog-product' in html.lower(),
        }
        print('\nДетекторы:')
        for name, found in markers.items():
            print(f'  {"✓" if found else "✗"} {name}')

        if 'catalog-product' in html.lower():
            print('\n🎉 SUCCESS! selenium-driverless проходит Qrator!')
        elif '403' in title:
            print('\n⚠ HTTP 403. Qrator всё равно блокирует.')
        else:
            print('\n⚠ Странный результат — посмотри HTML.')


if __name__ == '__main__':
    default = 'https://www.dns-shop.ru/catalog/17a89a3916404e77/operativnaya-pamyat/'
    url = sys.argv[1] if len(sys.argv) > 1 else default
    asyncio.run(main(url))
