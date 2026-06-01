"""Email-уведомления: верификация почты + дублирование алертов.

Использует стандартный django.core.mail. SMTP-настройки берутся из settings
(EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, …).
В dev-режиме (EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend)
письма выводятся в stdout — никаких SMTP не нужно.
"""
from __future__ import annotations

import logging
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

_RESEND_COOLDOWN_MINUTES = 5  # не спамим повторными письмами


def is_email_configured() -> bool:
    """True если EMAIL_HOST задан (реальный SMTP) или используется console/file backend."""
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    # console/file бэкенды работают без SMTP
    if 'console' in backend or 'filebased' in backend or 'locmem' in backend:
        return True
    return bool(getattr(settings, 'EMAIL_HOST', ''))


def _site_url() -> str:
    url = getattr(settings, 'SITE_URL', '').rstrip('/')
    return url or 'http://localhost'


def generate_verify_token(user) -> str:
    """Генерирует новый токен верификации и сохраняет на пользователе."""
    token = secrets.token_urlsafe(32)
    user.email_verify_token = token
    user.email_verify_sent_at = timezone.now()
    user.save(update_fields=['email_verify_token', 'email_verify_sent_at'])
    return token


def send_verification_email(user) -> bool:
    """Отправляет письмо со ссылкой верификации.

    Возвращает True при успехе. Тихо возвращает False при ошибке
    (не должно ломать регистрацию).
    """
    if not user.email:
        return False

    # Cooldown: не шлём повторно, если письмо было недавно
    if user.email_verify_sent_at:
        elapsed = timezone.now() - user.email_verify_sent_at
        if elapsed.total_seconds() < _RESEND_COOLDOWN_MINUTES * 60:
            logger.debug(
                'Verification email cooldown for %s (%ds remaining)',
                user.email,
                _RESEND_COOLDOWN_MINUTES * 60 - elapsed.total_seconds(),
            )
            return False

    token = generate_verify_token(user)
    verify_url = f'{_site_url()}/verify-email?token={token}'

    subject = 'Подтвердите email — Scout'
    message = (
        f'Привет{", " + user.first_name if user.first_name else ""}!\n\n'
        f'Для подтверждения почты перейдите по ссылке:\n{verify_url}\n\n'
        f'Ссылка действительна 24 часа.\n\n'
        f'Если вы не регистрировались — просто проигнорируйте это письмо.'
    )
    html_message = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>Подтвердите email</title></head>
<body style="font-family:Inter,system-ui,sans-serif;background:#0A0A0A;color:#F5F5F5;padding:40px 20px;margin:0">
  <div style="max-width:480px;margin:0 auto;background:#141414;border:1px solid #2E2E2E;border-radius:12px;padding:32px">
    <h2 style="margin:0 0 8px;font-size:22px;font-weight:700;color:#F5F5F5">scout.</h2>
    <p style="color:#A3A3A3;font-size:13px;margin:0 0 24px">мониторинг цен на маркетплейсах</p>
    <h3 style="margin:0 0 16px;font-size:18px;color:#F5F5F5">Подтвердите ваш email</h3>
    <p style="color:#A3A3A3;font-size:15px;line-height:1.6;margin:0 0 24px">
      {'Привет, ' + user.first_name + '!' if user.first_name else 'Привет!'}<br>
      Нажмите кнопку, чтобы подтвердить адрес почты и активировать уведомления.
    </p>
    <a href="{verify_url}"
       style="display:inline-block;background:#A855F7;color:#fff;font-size:15px;font-weight:600;
              padding:12px 28px;border-radius:8px;text-decoration:none">
      Подтвердить email
    </a>
    <p style="color:#666666;font-size:12px;margin:24px 0 0;line-height:1.5">
      Ссылка действительна 24 часа.<br>
      Если вы не регистрировались — просто проигнорируйте письмо.
    </p>
  </div>
</body>
</html>"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Verification email sent to %s', user.email)
        return True
    except Exception as exc:
        logger.warning('Failed to send verification email to %s: %s', user.email, exc)
        return False


def send_password_reset_email(user, reset_url: str) -> bool:
    """Отправляет письмо со ссылкой сброса пароля.

    reset_url формируется во view (uid + token из default_token_generator).
    Возвращает True при успехе, тихо False при ошибке SMTP.
    """
    if not user.email:
        return False

    subject = 'Сброс пароля — Scout'
    message = (
        f'Привет{", " + user.first_name if user.first_name else ""}!\n\n'
        f'Вы запросили сброс пароля. Перейдите по ссылке, чтобы задать новый:\n{reset_url}\n\n'
        f'Ссылка действительна 3 дня.\n\n'
        f'Если вы не запрашивали сброс — просто проигнорируйте это письмо, '
        f'пароль останется прежним.'
    )
    html_message = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>Сброс пароля</title></head>
<body style="font-family:Inter,system-ui,sans-serif;background:#0A0A0A;color:#F5F5F5;padding:40px 20px;margin:0">
  <div style="max-width:480px;margin:0 auto;background:#141414;border:1px solid #2E2E2E;border-radius:12px;padding:32px">
    <h2 style="margin:0 0 8px;font-size:22px;font-weight:700;color:#F5F5F5">scout.</h2>
    <p style="color:#A3A3A3;font-size:13px;margin:0 0 24px">мониторинг цен на маркетплейсах</p>
    <h3 style="margin:0 0 16px;font-size:18px;color:#F5F5F5">Сброс пароля</h3>
    <p style="color:#A3A3A3;font-size:15px;line-height:1.6;margin:0 0 24px">
      {'Привет, ' + user.first_name + '!' if user.first_name else 'Привет!'}<br>
      Нажмите кнопку, чтобы задать новый пароль.
    </p>
    <a href="{reset_url}"
       style="display:inline-block;background:#A855F7;color:#fff;font-size:15px;font-weight:600;
              padding:12px 28px;border-radius:8px;text-decoration:none">
      Задать новый пароль
    </a>
    <p style="color:#666666;font-size:12px;margin:24px 0 0;line-height:1.5">
      Ссылка действительна 3 дня.<br>
      Если вы не запрашивали сброс — проигнорируйте письмо.
    </p>
  </div>
</body>
</html>"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Password reset email sent to %s', user.email)
        return True
    except Exception as exc:
        logger.warning('Failed to send password reset email to %s: %s', user.email, exc)
        return False


def send_notification_email(user, subject: str, message: str) -> bool:
    """Дублирует уведомление о цене на email пользователя.

    Вызывается из _dispatch_notification если notify_email=True и email_verified=True.
    """
    if not user.email or not user.notify_email or not user.email_verified:
        return False

    html_message = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family:Inter,system-ui,sans-serif;background:#0A0A0A;color:#F5F5F5;padding:40px 20px;margin:0">
  <div style="max-width:480px;margin:0 auto;background:#141414;border:1px solid #2E2E2E;border-radius:12px;padding:32px">
    <h2 style="margin:0 0 8px;font-size:22px;font-weight:700;color:#F5F5F5">scout.</h2>
    <p style="color:#A3A3A3;font-size:13px;margin:0 0 24px">мониторинг цен на маркетплейсах</p>
    <p style="font-size:15px;line-height:1.6;color:#F5F5F5;margin:0 0 24px">{message}</p>
    <a href="{_site_url()}/notifications"
       style="display:inline-block;background:#141414;color:#A855F7;font-size:14px;font-weight:600;
              padding:10px 22px;border-radius:8px;text-decoration:none;border:1px solid #A855F7">
      Открыть уведомления
    </a>
    <p style="color:#666666;font-size:12px;margin:24px 0 0">
      Отключить email-уведомления можно в <a href="{_site_url()}/settings"
      style="color:#A855F7;text-decoration:none">настройках</a>.
    </p>
  </div>
</body>
</html>"""

    try:
        send_mail(
            subject=f'Scout: {subject}',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Notification email sent to %s', user.email)
        return True
    except Exception as exc:
        logger.warning('Failed to send notification email to %s: %s', user.email, exc)
        return False
