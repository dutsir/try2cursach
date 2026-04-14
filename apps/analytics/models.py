from django.db import models

from apps.core.models import BaseModel
from apps.products.models import Product


class Anomaly(BaseModel):
    class Severity(models.TextChoices):
        LOW = 'low', 'Низкая'
        MEDIUM = 'medium', 'Средняя'
        HIGH = 'high', 'Высокая'

    class AnomalyType(models.TextChoices):
        SPIKE = 'spike', 'Резкий скачок'
        MANIPULATION = 'manipulation', 'Манипуляция (подъём перед скидкой)'
        CYCLIC = 'cyclic', 'Циклическое колебание'

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='anomalies',
        verbose_name='Товар',
    )
    detected_at = models.DateTimeField('Обнаружена', auto_now_add=True, db_index=True)
    anomaly_type = models.CharField(
        'Тип аномалии', max_length=50, choices=AnomalyType.choices,
    )
    severity = models.CharField(
        'Серьёзность', max_length=20, choices=Severity.choices,
    )
    description = models.TextField('Описание')
    resolved = models.BooleanField('Разрешена', default=False)

    class Meta:
        verbose_name = 'Аномалия'
        verbose_name_plural = 'Аномалии'
        ordering = ['-detected_at']

    def __str__(self) -> str:
        return f'[{self.severity}] {self.product.name} — {self.anomaly_type}'


class CurrencyRate(BaseModel):
    class CurrencyCode(models.TextChoices):
        USD = 'USD', 'Доллар США'
        EUR = 'EUR', 'Евро'
        CNY = 'CNY', 'Юань'

    currency_code = models.CharField(
        'Валюта', max_length=3, choices=CurrencyCode.choices, default=CurrencyCode.USD,
    )
    rate = models.DecimalField('Курс к рублю', max_digits=10, decimal_places=4)
    date = models.DateField('Дата курса', db_index=True)

    class Meta:
        verbose_name = 'Курс валюты'
        verbose_name_plural = 'Курсы валют'
        ordering = ['-date']
        unique_together = [('currency_code', 'date')]

    def __str__(self) -> str:
        return f'{self.currency_code} {self.rate} ({self.date})'


class PriceForecast(BaseModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='forecasts',
        verbose_name='Товар',
    )
    forecast_date = models.DateField('Дата прогноза')
    predicted_price = models.DecimalField('Прогнозная цена', max_digits=12, decimal_places=2)
    lower_bound = models.DecimalField(
        'Нижняя граница', max_digits=12, decimal_places=2, null=True, blank=True,
    )
    upper_bound = models.DecimalField(
        'Верхняя граница', max_digits=12, decimal_places=2, null=True, blank=True,
    )
    method = models.CharField('Метод', max_length=50, default='ARIMA')

    class Meta:
        verbose_name = 'Прогноз цены'
        verbose_name_plural = 'Прогнозы цен'
        ordering = ['product', 'forecast_date']
        unique_together = [('product', 'forecast_date', 'method')]

    def __str__(self) -> str:
        return f'{self.product.name}: {self.predicted_price}₽ на {self.forecast_date}'


class AnalyticsSnapshot(BaseModel):
    """Сохранённый снимок агрегированной аналитики (отчёты, не сырые цены).

    Сырые данные по-прежнему в PriceHistory, Anomaly, PriceForecast, CurrencyRate.
    Здесь — вычисленные сводки для дашборда и истории «как было на дату».
    """

    class Kind(models.TextChoices):
        FULL_DASHBOARD = 'full_dashboard', 'Полный дашборд'
        CLUSTERS = 'clusters', 'Кластеры'
        CATEGORY_INDEX = 'category_index', 'Индекс по категориям'
        PARSING_METRICS = 'parsing_metrics', 'Метрики парсинга'
        DEALS_TOP = 'deals_top', 'Топ выгодных'
        ANOMALIES_SUMMARY = 'anomalies_summary', 'Сводка по аномалиям'
        HEATMAP = 'heatmap', 'Тепловая карта'
        SENSITIVITY = 'sensitivity', 'Чувствительность к валюте'

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
