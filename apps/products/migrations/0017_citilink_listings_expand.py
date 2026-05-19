from __future__ import annotations

from django.db import migrations


# Привязки для существующих категорий, у которых ещё нет CategoryListing
# для Citilink. Slug-и подобраны по аналогии с уже работающими записями:
#   pamyat-dlya-serverov, processory-dlya-serverov  -> servernye-* идут с
#   суффиксом '-dlya-serverov'; setevye-hranilischa-nas — общепринятый slug.
#
# Записи, slug которых на 100% не подтверждён, заводятся с is_active=False —
# они не пойдут в парсинг, но появятся в админке, и их можно включить после
# ручной проверки или после корректировки через
#   `python manage.py citilink_validate_listings --fix old=new`.
LISTINGS: list[tuple[str, str, bool]] = [
    # category.slug, citilink external_path, is_active
    ('setevye-karty', 'setevye-karty', True),
    ('setevye-hranilisha', 'setevye-hranilischa-nas', True),
    ('platy-rasshireniya', 'platy-rasshireniya', True),
    ('vneshnie-opticheskie-privody', 'vneshnie-opticheskie-privody', True),
    ('mikrokompyutery', 'mini-pk', True),
    ('sobrannyepk', 'sistemnye-bloki', True),
    ('servernye-bloki-pitaniya', 'bloki-pitaniya-dlya-serverov', True),
    ('servernye-materinskie-platy', 'materinskie-platy-dlya-serverov', True),
    ('servernye-korpusa', 'korpusa-dlya-serverov', True),
    ('servernye-nakopiteli', 'ssd-dlya-serverov', True),
    # Низкая уверенность: добавляем неактивными, slug нужно проверить
    # вручную в админке или через citilink_validate_listings.
    ('servernye-kabeli-i-perehodniki', 'kabeli-dlya-serverov', False),
    ('servernye-napravlyayushchie', 'servernye-napravlyayushchie', False),
    ('adaptery-dlya-nakopitelej', 'adaptery-dlya-zhestkih-diskov', False),
    ('korziny-dlya-nakopitelej', 'korziny-dlya-nakopiteley', False),
    ('mnogofunkcionalnye-paneli', 'mnogofunkcionalnye-paneli', False),
    ('aksessuary-dlya-materinskih-plat', 'aksessuary-dlya-materinskih-plat', False),
    ('aksessuary-dlya-servernyh-korpusov', 'aksessuary-dlya-servernyh-korpusov', False),
]


def add_listings(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    CategoryListing = apps.get_model('products', 'CategoryListing')

    for cat_slug, path, is_active in LISTINGS:
        cat = Category.objects.filter(slug=cat_slug).first()
        if cat is None:
            continue
        # Не перезаписываем, если запись уже есть — пользователь мог уже
        # подправить slug руками.
        CategoryListing.objects.get_or_create(
            category=cat,
            source='citilink',
            defaults={'external_path': path, 'is_active': is_active},
        )


def remove_listings(apps, schema_editor):
    CategoryListing = apps.get_model('products', 'CategoryListing')
    paths = [p for _, p, _ in LISTINGS]
    CategoryListing.objects.filter(source='citilink', external_path__in=paths).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0016_remove_offer_offer_source_mpn_idx'),
    ]

    operations = [
        migrations.RunPython(add_listings, remove_listings),
    ]
