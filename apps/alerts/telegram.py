"""Telegram-дублирование уведомлений.

Бот не может писать пользователю по @username — Telegram Bot API требует
chat_id, который доступен только после того, как пользователь сам написал боту.
Поэтому связываем аккаунт сайта с Telegram через код привязки:

1. Пользователь жмёт «Подключить Telegram» — генерируем короткий код.
2. Пишет боту `/start <код>` (или просто код).
3. Periodic-задача `task_poll_telegram_updates` забирает getUpdates, находит код,
   сохраняет chat_id + username на пользователе.

Webhook не используется (нет публичного HTTPS на VPS) — только polling.
Всё работает только при TELEGRAM_ENABLED=1 и заданном TELEGRAM_BOT_TOKEN.
"""
from __future__ import annotations

import logging
import secrets
import string

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Ключ в Redis, где храним offset getUpdates (чтобы не обрабатывать апдейты дважды).
_OFFSET_CACHE_KEY = 'telegram:updates_offset'
_CODE_ALPHABET = string.ascii_uppercase + string.digits


def is_configured() -> bool:
    return bool(settings.TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN)


def _api_url(method: str) -> str:
    return f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}'


def generate_link_code(user) -> str:
    """Создаёт и сохраняет на пользователе новый код привязки с TTL."""
    code = ''.join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
    ttl = timezone.timedelta(minutes=settings.TELEGRAM_LINK_CODE_TTL_MINUTES)
    user.telegram_link_code = code
    user.telegram_link_expires_at = timezone.now() + ttl
    user.save(update_fields=['telegram_link_code', 'telegram_link_expires_at'])
    return code


def send_message(chat_id: str, text: str) -> bool:
    """Отправляет сообщение в Telegram. Возвращает True при успехе.

    Тихо возвращает False, если интеграция не настроена или chat_id пуст —
    отправка не должна ломать основной поток уведомлений.
    """
    if not is_configured() or not chat_id:
        return False
    try:
        resp = requests.post(
            _api_url('sendMessage'),
            json={'chat_id': chat_id, 'text': text, 'disable_web_page_preview': False},
            timeout=settings.TELEGRAM_API_TIMEOUT,
        )
        if resp.status_code == 200 and resp.json().get('ok'):
            return True
        logger.warning('Telegram sendMessage failed: %s %s', resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        logger.warning('Telegram sendMessage error: %s', exc)
    return False


def _extract_code(text: str) -> str | None:
    """Достаёт код привязки из текста сообщения (`/start CODE` или просто `CODE`)."""
    if not text:
        return None
    parts = text.strip().split()
    if not parts:
        return None
    if parts[0].lower() in ('/start', 'start') and len(parts) >= 2:
        return parts[1].strip().upper()
    if len(parts) == 1 and parts[0].startswith('/'):
        return None
    return parts[0].strip().upper()


def _link_user_by_code(code: str, chat_id: str, username: str) -> bool:
    from apps.core.models import User

    if not code:
        return False
    user = (
        User.objects
        .filter(telegram_link_code=code, telegram_link_expires_at__gte=timezone.now())
        .first()
    )
    if not user:
        return False
    user.telegram_chat_id = str(chat_id)
    user.telegram_username = username or ''
    user.telegram_linked_at = timezone.now()
    user.notify_telegram = True
    user.telegram_link_code = ''
    user.telegram_link_expires_at = None
    user.save(update_fields=[
        'telegram_chat_id', 'telegram_username', 'telegram_linked_at',
        'notify_telegram', 'telegram_link_code', 'telegram_link_expires_at',
    ])
    send_message(
        chat_id,
        f'Готово! Аккаунт «{user.username}» привязан. '
        'Теперь уведомления о ценах будут дублироваться сюда.',
    )
    logger.info('Telegram linked: user=%s chat_id=%s', user.username, chat_id)
    return True


def poll_updates() -> dict:
    """Забирает новые getUpdates и привязывает пользователей по коду.

    Offset хранится в кэше, поэтому каждый апдейт обрабатывается один раз.
    """
    if not is_configured():
        return {'ok': False, 'reason': 'not_configured'}

    offset = cache.get(_OFFSET_CACHE_KEY)
    params = {'timeout': 0, 'allowed_updates': ['message']}
    if offset is not None:
        params['offset'] = offset

    try:
        resp = requests.get(
            _api_url('getUpdates'), params=params,
            timeout=settings.TELEGRAM_API_TIMEOUT,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Telegram getUpdates error: %s', exc)
        return {'ok': False, 'reason': 'request_error'}

    if not data.get('ok'):
        logger.warning('Telegram getUpdates not ok: %s', str(data)[:200])
        return {'ok': False, 'reason': 'api_not_ok'}

    updates = data.get('result', [])
    linked = 0
    max_update_id = None
    for upd in updates:
        max_update_id = upd['update_id']
        message = upd.get('message') or {}
        chat = message.get('chat') or {}
        chat_id = chat.get('id')
        username = chat.get('username') or ''
        code = _extract_code(message.get('text', ''))
        if chat_id and code and _link_user_by_code(code, chat_id, username):
            linked += 1

    if max_update_id is not None:
        # offset = последний обработанный update_id + 1
        cache.set(_OFFSET_CACHE_KEY, max_update_id + 1, timeout=None)

    return {'ok': True, 'updates': len(updates), 'linked': linked}
