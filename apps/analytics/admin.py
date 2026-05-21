from django.contrib import admin

from .models import AnalyticsSnapshot


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'scope_key', 'created_at')
    list_filter = ('kind',)
    readonly_fields = ('created_at', 'updated_at', 'parameters', 'summary', 'payload')
    search_fields = ('scope_key',)
