#!/usr/bin/env python3
"""Экспорт cookies dns-shop.ru из основного Chrome-профиля хоста.

Зачем: DNS за Qrator. Холодный профиль парсера получает жёсткий HTTP 403 —
у него нет clearance-куки (qrator_jsid2/qrator_jsr/qrator_ssid2). В обычном
браузере пользователя эти куки есть (он проходит проверку как живой человек).
Скрипт расшифровывает их (Chrome на Linux шифрует значения через keyring, v11)
и кладёт в JSON, который парсер инжектит в свою сессию через CDP Network.setCookie
ДО навигации — Qrator видит валидную сессию и пропускает запрос.

Запуск (на хосте, в графической сессии с разблокированным keyring):
    venv/bin/python scripts/export_dns_cookies.py

Куки Qrator живут недолго — повторяй экспорт, если парсер снова ловит 403.
Зависимость: browser-cookie3 (pip install browser-cookie3).
"""
from __future__ import annotations

import json
import os
import sys

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'var', 'chrome_profiles', 'dns_cookies.json',
)


def main() -> int:
    try:
        import browser_cookie3 as bc
    except ImportError:
        print('Нет browser-cookie3. Установи: venv/bin/pip install browser-cookie3', file=sys.stderr)
        return 1

    try:
        jar = bc.chrome(domain_name='dns-shop.ru')
    except Exception as exc:  # noqa: BLE001
        print(f'Не удалось прочитать куки Chrome: {exc}', file=sys.stderr)
        print('Проверь: Chrome закрыт? keyring разблокирован? DBUS_SESSION_BUS_ADDRESS задан?', file=sys.stderr)
        return 1

    cookies = []
    for c in jar:
        rest = getattr(c, '_rest', {}) or {}
        http_only = any(k.lower() == 'httponly' for k in rest)
        same_site = next((rest[k] for k in rest if k.lower() == 'samesite'), None)
        item = {
            'name': c.name,
            'value': c.value or '',
            'domain': c.domain,
            'path': c.path or '/',
            'secure': bool(c.secure),
            'httpOnly': http_only,
        }
        if c.expires:
            item['expires'] = float(c.expires)
        if same_site in ('Strict', 'Lax', 'None'):
            item['sameSite'] = same_site
        cookies.append(item)

    if not cookies:
        print('Куки dns-shop.ru не найдены. Открой dns-shop.ru в Chrome и пройди проверку.', file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

    qrator = [c['name'] for c in cookies if 'qrator' in c['name'].lower()]
    print(f'Сохранено {len(cookies)} cookies → {OUT_PATH}')
    print(f'Qrator clearance: {", ".join(qrator) if qrator else "НЕ НАЙДЕНЫ (403 вероятен)"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
