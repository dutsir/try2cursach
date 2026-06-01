import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _best_actual_price(product):
    """Минимальная актуальная цена среди офферов товара (лучшее предложение).

    Возвращает PriceHistory-запись или None. Берём min по цене, а не последнюю
    по времени — подписка должна срабатывать на самое выгодное предложение.
    """
    from apps.prices.models import PriceHistory

    return (
        PriceHistory.objects
        .filter(product=product, is_actual=True, price__gt=0)
        .order_by('price')
        .first()
    )


def _dispatch_notification(sub, message: str, ntype: str) -> None:
    """Создаёт Notification и дублирует в Telegram/Email, если пользователь подключил."""
    from .models import Notification
    from .telegram import send_message
    from .email_notify import send_notification_email

    Notification.objects.create(
        user=sub.user,
        subscription=sub,
        product=sub.product,
        type=ntype,
        message=message,
    )
    sub.last_notified_at = timezone.now()
    sub.save(update_fields=['last_notified_at', 'updated_at'])

    user = sub.user

    # Telegram
    if user.notify_telegram and user.telegram_chat_id:
        send_message(user.telegram_chat_id, message)

    # Email
    type_labels = {
        'price_drop': 'Цена достигла цели',
        'anomaly': 'Резкое снижение цены',
        'availability': 'Товар появился в наличии',
    }
    subject = type_labels.get(ntype, 'Уведомление о цене')
    send_notification_email(user, subject, message)


@shared_task
def task_check_subscriptions() -> dict:
    from .models import Subscription

    cooldown = timezone.timedelta(hours=settings.SUBSCRIPTION_NOTIFY_COOLDOWN_HOURS)
    now = timezone.now()

    subscriptions = (
        Subscription.objects
        .filter(is_active=True)
        .select_related('user', 'product')
    )

    notified = 0
    for sub in subscriptions:
        # Cooldown: не уведомляем повторно, пока условие держится.
        if sub.last_notified_at and (now - sub.last_notified_at) < cooldown:
            continue

        message: str | None = None
        ntype = sub.notify_on

        if sub.notify_on == Subscription.NotifyOn.PRICE_DROP:
            best = _best_actual_price(sub.product)
            if best and best.price <= sub.target_price:
                message = (
                    f'Цена на «{sub.product.name}» упала до {best.price}₽ '
                    f'(ваша целевая: {sub.target_price}₽). '
                    f'Ссылка: {sub.product.url}'
                )

        elif sub.notify_on == Subscription.NotifyOn.AVAILABILITY:
            if sub.product.offers.filter(is_available=True).exists():
                message = (
                    f'Товар «{sub.product.name}» появился в наличии. '
                    f'Ссылка: {sub.product.url}'
                )

        elif sub.notify_on == Subscription.NotifyOn.ANOMALY:
            from apps.prices.stats import compute_product_price_stats

            best = _best_actual_price(sub.product)
            current = int(best.price) if best else None
            stats = compute_product_price_stats(sub.product, current_price=current)
            if stats.drop_alert:
                pct = stats.drop_alert_pct or 0
                message = (
                    f'Резкое снижение цены на «{sub.product.name}»: '
                    f'-{pct}% от обычной. Похоже на распродажу. '
                    f'Ссылка: {sub.product.url}'
                )

        if message:
            _dispatch_notification(sub, message, ntype)
            notified += 1
            logger.info('Уведомление (%s) для %s: %s', ntype, sub.user.username, sub.product.name)

    logger.info('Проверка подписок завершена: уведомлений создано %d', notified)
    return {'notified': notified}


@shared_task
def task_poll_telegram_updates() -> dict:
    """Забирает getUpdates и привязывает Telegram-аккаунты по коду.

    Запускается периодически (см. beat). No-op, если TELEGRAM_ENABLED=0.
    """
    from .telegram import poll_updates

    return poll_updates()
