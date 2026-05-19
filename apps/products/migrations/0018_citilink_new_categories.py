from __future__ import annotations

from django.db import migrations


# Новые категории + Citilink-привязки. DNS не добавляем: его slug требует
# хэш-префикс (например '17a89a3916404e77/...'), который без живой проверки
# выдумать нельзя — добавим вручную в админке.
#
# Родителя ищем по name, потому что slug у групп кириллический (создан
# slugify(..., allow_unicode=True) в миграции 0007), и в исходниках его
# проще указать как Unicode-строку русского названия.
#
# Формат: (название, slug, parent name, citilink_path)
NEW_CATEGORIES: list[tuple[str, str, str, str]] = [
    ('Наушники',               'naushniki',               'Периферия',             'naushniki'),
    ('Веб-камеры',             'veb-kamery',              'Периферия',             'veb-kamery'),
    ('Геймпады',               'gejmpady',                'Периферия',             'gejmpady'),
    ('Микрофоны',              'mikrofony',               'Периферия',             'mikrofony'),
    ('Акустические системы',   'akusticheskie-sistemy',   'Периферия',             'akusticheskie-sistemy'),
    ('Внешние жёсткие диски',  'vneshnie-zhestkie-diski', 'Накопители',            'vneshnie-zhestkie-diski'),
    ('USB-флеш-накопители',    'flash-nakopiteli',        'Накопители',            'flash-nakopiteli'),
    ('Карты памяти',           'karty-pamyati',           'Накопители',            'karty-pamyati'),
    ('ИБП',                    'ibp',                     'Комплектующие ПК',      'ibp'),
]


def _ensure_parent(Category, parent_name: str):
    return Category.objects.filter(name=parent_name, parent__isnull=True).first()


def add_categories(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    CategoryListing = apps.get_model('products', 'CategoryListing')

    for name, slug, parent_name, cit_path in NEW_CATEGORIES:
        parent = _ensure_parent(Category, parent_name)
        # Если parent не нашёлся (slug изменился) — просто создаём в корне,
        # пользователь сможет переподвесить в админке.
        cat, _ = Category.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'parent': parent, 'is_active': True},
        )
        if parent is not None and cat.parent_id is None:
            cat.parent = parent
            cat.save(update_fields=['parent'])

        CategoryListing.objects.get_or_create(
            category=cat,
            source='citilink',
            defaults={'external_path': cit_path, 'is_active': True},
        )


def remove_categories(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    CategoryListing = apps.get_model('products', 'CategoryListing')

    slugs = [s for _, s, _, _ in NEW_CATEGORIES]
    cats = Category.objects.filter(slug__in=slugs)
    CategoryListing.objects.filter(category__in=cats).delete()
    cats.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0017_citilink_listings_expand'),
    ]

    operations = [
        migrations.RunPython(add_categories, remove_categories),
    ]
