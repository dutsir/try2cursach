"""Pure-HTTP решатель Qrator-челленджа для dns-shop.ru.

Делает то же, что ручной экспорт cookies из реального Chrome
(scripts/export_dns_cookies.py), но без браузера: GET → challenge-кука
qrator_jsr → решение proof-of-work → POST /__qrator/validate с
fingerprint-payload → clearance-кука qrator_jsid2.

Возвращает ВЕСЬ набор cookies сессии (а не только jsid2), потому что
парсеру для запросов нужны все qrator_*-куки сразу.

ВАЖНО: clearance Qrator привязан к IP, который решал челлендж. Поэтому
вызов solve_clearance и последующие запросы к DNS обязаны идти через
один и тот же прокси/IP.
"""
from __future__ import annotations

import base64
import hashlib
import importlib
import json
import os
import random
import time
import urllib.parse

_FP_DIR = os.path.dirname(os.path.abspath(__file__))
_fp_cache: dict[str, dict] = {}


class QratorSolveError(RuntimeError):
    """Не удалось получить clearance-куку (протух revision, сменился протокол, бан IP)."""


def _load_fingerprint(name: str) -> dict:
    if name not in _fp_cache:
        path = os.path.join(_FP_DIR, name)
        with open(path, encoding='utf-8') as f:
            _fp_cache[name] = json.load(f)
    return _fp_cache[name]


def _md5(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _xor(t: str, e: str) -> str:
    w = len(e)
    return ''.join(chr(ord(t[i]) ^ ord(e[i % w])) for i in range(len(t)))


def _solve_pow(session_nonce: str) -> int:
    idx = 0
    while True:
        idx += 1
        if _md5(session_nonce + str(idx))[:2] == '00':
            return idx


def _fp_hash(ua: str, pow_val: int, nonce: str) -> str:
    alphabet = '0123456789abcdef'
    salt = ''.join(random.choice(alphabet) for _ in range(4))
    ua_data = json.loads(ua)
    ua_data['time'] = time.time()
    ua_str = json.dumps(ua_data, ensure_ascii=False)
    key = _md5(salt + str(nonce) + str(pow_val))
    return 'v1$' + salt + '$' + _b64(_xor(ua_str, key))


def _cookies_to_dict(session: object) -> dict[str, str]:
    cookies = getattr(session, 'cookies', None)
    if cookies is None:
        return {}
    for attr in ('get_dict',):
        fn = getattr(cookies, attr, None)
        if callable(fn):
            try:
                return dict(fn())
            except Exception:
                pass
    jar = getattr(cookies, 'jar', None)
    if jar is not None:
        try:
            return {c.name: c.value for c in jar}
        except Exception:
            pass
    try:
        return dict(cookies)
    except Exception:
        return {}


def solve_clearance(
    *,
    site: str,
    fingerprint: str,
    user_agent: str,
    client_hints: str,
    revision: str,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict[str, str]:
    """Решает Qrator-челлендж и возвращает dict всех cookies сессии.

    Бросает QratorSolveError, если challenge-кука не выдана или validate
    не вернул 200 (обычно — протух revision или забанен IP).
    """
    cr = importlib.import_module('curl_cffi.requests')
    domain = site.split('://')[1].split('/')[0]

    session = cr.Session(impersonate='chrome')
    if proxy:
        session.proxies = {'all': proxy}

    session.get(site, timeout=timeout)

    jsr = session.cookies.get('qrator_jsr')
    if not jsr:
        # Qrator не выдал challenge — либо IP уже доверенный (тогда cookies
        # сессии и так годны), либо запрос не дошёл. Возвращаем что есть.
        existing = _cookies_to_dict(session)
        if any('qrator' in k.lower() for k in existing):
            return existing
        raise QratorSolveError(
            'Qrator не выдал qrator_jsr challenge-куку и нет готовых '
            'qrator-кук. Запрос не дошёл до Qrator или IP неожиданный.'
        )

    parts = jsr.split('-')
    nonce, qsessid = parts[0], parts[1]
    pow_val = _solve_pow(nonce)

    finger = _load_fingerprint(fingerprint)
    json_data = {
        **{k: _fp_hash(finger[k], pow_val, nonce) for k in finger},
        'vx': revision,
        'version': '2',
        'state': 'base',
    }
    qp = urllib.parse.urlencode(
        {'pow': pow_val, 'nonce': nonce, 'qsessid': qsessid}, safe='|/=+'
    )
    validate_url = f'https://{domain}/__qrator/validate?{qp}'

    resp = session.post(
        url=validate_url,
        json=json_data,
        headers={
            'sec-ch-ua': client_hints,
            'user-agent': user_agent,
            'x-qrator-revision': f'{revision}-m',
            'x-qrator-token': jsr.replace('-00', ''),
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise QratorSolveError(
            f'/__qrator/validate вернул {resp.status_code} — вероятно протух '
            f'revision ({revision}) или сменился протокол Qrator.'
        )

    cookies = _cookies_to_dict(session)
    if 'qrator_jsid2' not in cookies and not any('qrator' in k.lower() for k in cookies):
        raise QratorSolveError('validate вернул 200, но clearance-кука qrator_jsid2 не появилась.')
    return cookies
