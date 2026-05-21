from django.db import models

from apps.core.models import BaseModel


class AnalyticsSnapshot(BaseModel):

    class Kind(models.TextChoices):
        FULL_DASHBOARD = 'full_dashboard', 'Полный дашборд'
        CLUSTERS = 'clusters', 'Кластеры'
        CATEGORY_INDEX = 'category_index', 'Индекс по категориям'
        PARSING_METRICS = 'parsing_metrics', 'Метрики парсинга'
        DEALS_TOP = 'deals_top', 'Топ выгодных'
        HEATMAP = 'heatmap', 'Тепловая карта'

    kind = models.CharField('Тип снимка', max_length=40, choices=Kind.choices, db_index=True)
    scope_key = models.CharField(
        'Область',
        max_length=200,
        blank=True,
        default='',
        help_text='Например slug категории или пусто для «все».',
    )
    parameters = models.JSONField('Параметры расчёта', default=dict, blank=True)
    summary = models.JSONField(
        'Краткая сводка',
        default=dict,
        blank=True,
        help_text='Числа для списков и виджетов без разворачивания payload.',
    )
    payload = models.JSONField('Полные данные', default=dict)

    class Meta:
        verbose_name = 'Снимок аналитики'
        verbose_name_plural = 'Снимки аналитики'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['kind', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'{self.get_kind_display()} @ {self.created_at:%Y-%m-%d %H:%M}'
