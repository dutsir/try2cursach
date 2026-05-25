from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.products.models import Category, Offer, Product


class PriceHistory(BaseModel):
    class Source(models.TextChoices):
        DNS = 'dns', 'DNS'
        OZON = 'ozon', 'Ozon'
        CITILINK = 'citilink', 'Ситилинк'
        WB = 'wb', 'Wildberries'

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='price_history',
        verbose_name='Товар',
    )

    offer = models.ForeignKey(
        Offer,
        on_delete=models.CASCADE,
        related_name='price_history',
        verbose_name='Оффер',
        null=True,
        blank=True,
    )
    price = models.DecimalField('Цена', max_digits=12, decimal_places=2)
    old_price = models.DecimalField(
        'Старая цена (до скидки)', max_digits=12, decimal_places=2, null=True, blank=True,
    )
    timestamp = models.DateTimeField('Время фиксации', db_index=True)
    is_actual = models.BooleanField('Актуальна', default=True)
    source = models.CharField(
        'Источник', max_length=50, choices=Source.choices, default=Source.DNS,
    )

    class Meta:
        verbose_name = 'Запись цены'
        verbose_name_plural = 'История цен'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['product', '-timestamp']),
            models.Index(fields=['offer', '-timestamp']),
            models.Index(fields=['product', 'source', 'is_actual']),
        ]

    def __str__(self) -> str:
        return f'{self.product.name}: {self.price}₽ ({self.timestamp:%d.%m.%Y %H:%M})'


class ParseRun(BaseModel):

    class Source(models.TextChoices):
        DNS = 'dns', 'DNS'
        OZON = 'ozon', 'Ozon'
        CITILINK = 'citilink', 'Ситилинк'
        WB = 'wb', 'Wildberries'

    class Status(models.TextChoices):
        RUNNING = 'running', 'Идёт'
        OK = 'ok', 'Успех'
        EMPTY = 'empty', 'Пусто'
        ERROR = 'error', 'Ошибка'

    source = models.CharField('Источник', max_length=32, choices=Source.choices, db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='parse_runs',
        verbose_name='Категория',
        null=True,
        blank=True,
    )
    status = models.CharField(
        'Статус', max_length=16, choices=Status.choices, default=Status.RUNNING, db_index=True,
    )
    started_at = models.DateTimeField('Начало', default=timezone.now, db_index=True)
    finished_at = models.DateTimeField('Конец', null=True, blank=True)
    parsed_count = models.PositiveIntegerField('Карточек спарсено', default=0)
    saved_offers = models.PositiveIntegerField('Офферов сохранено', default=0)
    new_offers = models.PositiveIntegerField('Новых офферов', default=0)
    new_products = models.PositiveIntegerField('Новых мастер-товаров', default=0)
    saved_prices = models.PositiveIntegerField('Новых записей цен', default=0)
    error_message = models.TextField('Ошибка', blank=True, default='')

    class Meta:
        verbose_name = 'Прогон парсера'
        verbose_name_plural = 'Прогоны парсеров'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['source', '-started_at']),
        ]

    def __str__(self) -> str:
        cat = self.category.slug if self.category else '—'
        return f'{self.get_source_display()} / {cat} / {self.get_status_display()}'

    @property
    def duration_seconds(self) -> float | None:
        if not self.finished_at:
            return None
        return (self.finished_at - self.started_at).total_seconds()
