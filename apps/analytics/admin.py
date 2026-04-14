from django.contrib import admin

from .models import AnalyticsSnapshot, Anomaly, CurrencyRate, PriceForecast


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = ('product', 'anomaly_type', 'severity', 'detected_at', 'resolved')
    list_filter = ('severity', 'anomaly_type', 'resolved', 'detected_at')
    search_fields = ('product__name', 'description')
    raw_id_fields = ('product',)


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'scope_key', 'created_at')
    list_filter = ('kind',)
    readonly_fields = ('created_at', 'updated_at', 'parameters', 'summary', 'payload')
    search_fields = ('scope_key',)


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ('currency_code', 'rate', 'date', 'created_at')
    list_filter = ('currency_code',)


@admin.register(PriceForecast)
class PriceForecastAdmin(admin.ModelAdmin):
    list_display = ('product', 'forecast_date', 'predicted_price', 'method', 'created_at')
    raw_id_fields = ('product',)
