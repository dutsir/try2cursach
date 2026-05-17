from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.products.models import Product


class Subscription(BaseModel):
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
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        unique_together = ('user', 'product')

    def __str__(self) -> str:
        return f'{self.user} → {self.product.name} (≤ {self.target_price}₽)'


class Notification(BaseModel):
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
    message = models.TextField('Сообщение')
    sent_at = models.DateTimeField('Отправлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-sent_at']

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
        return sum(
            (item.product.best_offer.price if item.product.best_offer else 0) * item.quantity
            for item in self.items.all()
        )


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
