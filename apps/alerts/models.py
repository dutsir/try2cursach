from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.products.models import Product


class Subscription(BaseModel):

    class NotifyOn(models.TextChoices):
        PRICE_DROP = 'price_drop', 'Падение цены'
        ANOMALY = 'anomaly', 'Аномалия'
        AVAILABILITY = 'availability', 'Появление в наличии'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Пользователь',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Товар',
    )
    target_price = models.DecimalField(
        'Целевая цена', max_digits=12, decimal_places=2,
    )
    notify_on = models.CharField(
        'Условие уведомления', max_length=16,
        choices=NotifyOn.choices, default=NotifyOn.PRICE_DROP,
    )
    is_active = models.BooleanField('Активна', default=True)
    # Момент последнего срабатывания — для cooldown (не уведомляем повторно
    # каждый прогон, пока цена держится ниже целевой).
    last_notified_at = models.DateTimeField('Последнее уведомление', null=True, blank=True)

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        unique_together = ('user', 'product')
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.user} → {self.product.name} (≤ {self.target_price}₽)'


class Notification(BaseModel):

    class Type(models.TextChoices):
        PRICE_DROP = 'price_drop', 'Падение цены'
        ANOMALY = 'anomaly', 'Аномалия'
        AVAILABILITY = 'availability', 'Появление в наличии'
        INFO = 'info', 'Информация'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь',
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='Подписка',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='Товар',
    )
    type = models.CharField(
        'Тип', max_length=16, choices=Type.choices,
        default=Type.PRICE_DROP, db_index=True,
    )
    message = models.TextField('Сообщение')
    is_read = models.BooleanField('Прочитано', default=False, db_index=True)
    sent_at = models.DateTimeField('Отправлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self) -> str:
        return f'Уведомление для {self.user} ({self.sent_at:%d.%m.%Y %H:%M})'


class Wishlist(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist',
        verbose_name='Пользователь',
    )
    title = models.CharField('Название', max_length=255, default='Мой вишлист')
    description = models.TextField('Описание', blank=True)

    class Meta:
        verbose_name = 'Вишлист'
        verbose_name_plural = 'Вишлисты'

    def __str__(self) -> str:
        return f'{self.user} — {self.title}'

    @property
    def total_price(self) -> float:
        from apps.prices.models import PriceHistory

        total = 0.0
        for item in self.items.all():
            best = (
                PriceHistory.objects
                .filter(product=item.product, is_actual=True)
                .order_by('price')
                .first()
            )
            if best:
                total += float(best.price) * item.quantity
        return total


class WishlistItem(BaseModel):
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Вишлист',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlist_items',
        verbose_name='Товар',
    )
    quantity = models.PositiveIntegerField('Количество', default=1)
    note = models.TextField('Заметка', blank=True)
    added_at = models.DateTimeField('Добавлен', auto_now_add=True)

    class Meta:
        verbose_name = 'Товар в вишлисте'
        verbose_name_plural = 'Товары в вишлисте'
        unique_together = ('wishlist', 'product')
        ordering = ['-added_at']

    def __str__(self) -> str:
        return f'{self.product.name} × {self.quantity}'
