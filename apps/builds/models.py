from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.products.models import Product


class Build(BaseModel):
    """Сборка ПК пользователя: набор выбранных компонентов по слотам.

    Раньше сборка жила только в localStorage фронта. Теперь храним на бэке,
    чтобы она переживала смену устройства и была доступна для аналитики.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='builds',
        verbose_name='Пользователь',
    )
    name = models.CharField('Название', max_length=255, default='Моя сборка')

    class Meta:
        verbose_name = 'Сборка ПК'
        verbose_name_plural = 'Сборки ПК'
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'{self.user} — {self.name}'

    @property
    def total_price(self) -> float:
        return float(
            sum(
                (item.price_snapshot or 0) * item.quantity
                for item in self.items.all()
            )
        )


class BuildItem(BaseModel):

    class Slot(models.TextChoices):
        CPU = 'cpu', 'Процессор'
        MB = 'mb', 'Материнская плата'
        GPU = 'gpu', 'Видеокарта'
        RAM = 'ram', 'Оперативная память'
        PSU = 'psu', 'Блок питания'
        CASE = 'case', 'Корпус'
        SSD = 'ssd', 'SSD'
        HDD = 'hdd', 'Жёсткий диск'

    build = models.ForeignKey(
        Build,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Сборка',
    )
    slot = models.CharField('Слот', max_length=8, choices=Slot.choices)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='build_items',
        verbose_name='Товар',
    )
    # Цена на момент добавления (snapshot). Актуальную цену фронт берёт из best_offer.
    price_snapshot = models.DecimalField(
        'Цена при добавлении', max_digits=12, decimal_places=2, default=0,
    )
    quantity = models.PositiveIntegerField('Количество', default=1)

    class Meta:
        verbose_name = 'Компонент сборки'
        verbose_name_plural = 'Компоненты сборки'
        ordering = ['slot']
        constraints = [
            models.UniqueConstraint(fields=['build', 'slot'], name='build_slot_unique'),
        ]

    def __str__(self) -> str:
        return f'{self.get_slot_display()}: {self.product.name}'
