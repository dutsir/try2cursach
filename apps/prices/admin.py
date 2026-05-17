from django.contrib import admin

from .models import ParseRun, PriceHistory


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'offer', 'price', 'old_price', 'source', 'is_actual', 'timestamp')
    list_filter = ('source', 'is_actual', 'timestamp')
    search_fields = ('product__name',)
    raw_id_fields = ('product', 'offer')
    date_hierarchy = 'timestamp'


@admin.register(ParseRun)
class ParseRunAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'source', 'category', 'status', 'parsed_count', 'saved_offers',
        'new_offers', 'new_products', 'saved_prices', 'started_at', 'duration_seconds',
    )
    list_filter = ('source', 'status', 'started_at')
    search_fields = ('category__name', 'category__slug', 'error_message')
    raw_id_fields = ('category',)
    readonly_fields = ('started_at', 'finished_at')
    date_hierarchy = 'started_at'

    @admin.display(description='Сек.')
    def duration_seconds(self, obj: ParseRun) -> str:
        d = obj.duration_seconds
        return f'{d:.1f}' if d is not None else '—'
