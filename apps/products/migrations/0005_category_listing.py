

import django.db.models.deletion
from django.db import migrations, models


def copy_category_store_fields_to_listings(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    CategoryListing = apps.get_model('products', 'CategoryListing')
    for c in Category.objects.all():
        dns = (getattr(c, 'dns_category_slug', None) or '').strip()
        if dns:
            CategoryListing.objects.update_or_create(
                category_id=c.pk,
                source='dns',
                defaults={'external_path': dns, 'is_active': bool(c.is_active)},
            )
        cit = (getattr(c, 'citilink_catalog_path', None) or '').strip()
        if cit:
            CategoryListing.objects.update_or_create(
                category_id=c.pk,
                source='citilink',
                defaults={'external_path': cit, 'is_active': bool(c.is_active)},
            )
        oz = (getattr(c, 'ozon_category_url', None) or '').strip()
        if oz:
            CategoryListing.objects.update_or_create(
                category_id=c.pk,
                source='ozon',
                defaults={'external_path': oz, 'is_active': bool(c.is_active)},
            )


def restore_category_fields_from_listings(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    CategoryListing = apps.get_model('products', 'CategoryListing')
    for c in Category.objects.all():
        updates: dict[str, str] = {}
        for lst in CategoryListing.objects.filter(category_id=c.pk):
            if lst.source == 'dns':
                updates['dns_category_slug'] = lst.external_path
            elif lst.source == 'citilink':
                updates['citilink_catalog_path'] = lst.external_path
            elif lst.source == 'ozon':
                updates['ozon_category_url'] = lst.external_path
        if updates:
            Category.objects.filter(pk=c.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_alter_product_vendor_code_offer'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoryListing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('source', models.CharField(choices=[('dns', 'DNS'), ('citilink', 'Ситилинк'), ('ozon', 'Ozon')], db_index=True, max_length=32, verbose_name='Магазин')),
                ('external_path', models.CharField(help_text='DNS: slug вида 17a89aab16404e77/videokarty. Ситилинк: относительный путь или полный URL каталога. Ozon: полный URL раздела (без обязательной валидации URL — допускаются длинные пути).', max_length=1024, verbose_name='Каталог у магазина')),
                ('is_active', models.BooleanField(default=True, verbose_name='Учитывать при парсинге')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='listings', to='products.category', verbose_name='Категория')),
            ],
            options={
                'verbose_name': 'Каталог у магазина',
                'verbose_name_plural': 'Каталоги у магазинов',
                'ordering': ['category_id', 'source'],
                'indexes': [models.Index(fields=['source', 'is_active'], name='products_ca_source_eaddfd_idx')],
                'constraints': [models.UniqueConstraint(fields=('category', 'source'), name='category_listing_source_unique')],
            },
        ),
        migrations.RunPython(copy_category_store_fields_to_listings, restore_category_fields_from_listings),
        migrations.RemoveField(
            model_name='category',
            name='citilink_catalog_path',
        ),
        migrations.RemoveField(
            model_name='category',
            name='dns_category_slug',
        ),
        migrations.RemoveField(
            model_name='category',
            name='ozon_category_url',
        ),
    ]
