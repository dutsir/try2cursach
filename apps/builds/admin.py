from django.contrib import admin

from .models import Build, BuildItem


class BuildItemInline(admin.TabularInline):
    model = BuildItem
    extra = 0
    autocomplete_fields = ('product',)


@admin.register(Build)
class BuildAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'updated_at')
    search_fields = ('user__username', 'name')
    inlines = [BuildItemInline]
