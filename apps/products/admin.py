from django.contrib import admin

from .models import Category, CategoryListing, Offer, Product


class CategoryListingInline(admin.TabularInline):
    model = CategoryListing
    extra = 0
    fields = ('source', 'external_path', 'is_active')
    ordering = ('source',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        'tree_name', 'slug', 'parent', 'listings_summary', 'products_count',
        'is_active', 'created_at',
    )
    list_filter = ('is_active', 'parent')
    list_editable = ('parent',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = (CategoryListingInline,)
    raw_id_fields = ('parent',)
    ordering = ('parent__name', 'name')

    @admin.display(description='Название (дерево)', ordering='name')
    def tree_name(self, obj: Category) -> str:
        depth = len(obj.ancestors())
        prefix = '— ' * depth
        return f'{prefix}{obj.name}'

    @admin.display(description='Товаров в ветке')
    def products_count(self, obj: Category) -> int:

        from .models import Product
        return Product.objects.filter(category_id__in=obj.descendants_ids()).count()

    @admin.display(description='Магазины (парсинг)')
    def listings_summary(self, obj: Category) -> str:
        qs = obj.listings.order_by('source')
        if not qs.exists():
            return '—'
        parts: list[str] = []
        for lst in qs:
            mark = '' if lst.is_active else ' (выкл.)'
            parts.append(f'{lst.get_source_display()}{mark}')
        return ', '.join(parts)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'parent':
            kwargs['queryset'] = Category.objects.order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class OfferInline(admin.TabularInline):
    model = Offer
    extra = 0
    fields = ('source', 'url', 'vendor_code', 'is_available', 'last_seen_at')
    readonly_fields = ('last_seen_at',)
    show_change_link = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'vendor_code', 'offers_count', 'is_active', 'last_parsed_at')
    list_filter = ('is_active', 'category')
    search_fields = ('name', 'vendor_code')
    raw_id_fields = ('category',)
    readonly_fields = ('last_parsed_at',)
    inlines = (OfferInline,)

    @admin.display(description='Офферов', ordering='offers__count')
    def offers_count(self, obj: Product) -> int:
        return obj.offers.count()


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ('product', 'source', 'vendor_code', 'is_available', 'last_seen_at')
    list_filter = ('source', 'is_available')
    search_fields = ('product__name', 'vendor_code', 'url')
    raw_id_fields = ('product',)
    readonly_fields = ('last_seen_at',)


@admin.register(CategoryListing)
class CategoryListingAdmin(admin.ModelAdmin):
    list_display = ('category', 'source', 'external_path_short', 'is_active', 'updated_at')
    list_filter = ('source', 'is_active')
    search_fields = ('category__name', 'category__slug', 'external_path')
    raw_id_fields = ('category',)
    ordering = ('category__slug', 'source')

    @admin.display(description='Путь')
    def external_path_short(self, obj: CategoryListing) -> str:
        s = obj.external_path or ''
        return (s[:80] + '…') if len(s) > 83 else s
