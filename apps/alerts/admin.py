from django.contrib import admin
from django.utils.html import format_html

from .models import Notification, Subscription, Wishlist, WishlistItem


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'target_price', 'is_active', 'created_at')
    list_filter = ('is_active',)
    raw_id_fields = ('user', 'product')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription', 'sent_at')
    list_filter = ('sent_at',)
    raw_id_fields = ('user', 'subscription')


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    fields = ('product', 'quantity', 'note', 'added_at')
    readonly_fields = ('added_at',)
    raw_id_fields = ('product',)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'items_count', 'total_price_display', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email', 'title')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    raw_id_fields = ('user',)
    inlines = (WishlistItemInline,)

    @admin.display(description='Товаров')
    def items_count(self, obj):
        return obj.items.count()

    @admin.display(description='Сумма')
    def total_price_display(self, obj):
        price = obj.total_price
        if price:
            return format_html('<b>{} ₽</b>', f'{price:,.0f}')
        return '—'
