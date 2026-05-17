

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_category_ozon_category_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='vendor_code',
            field=models.CharField(blank=True, db_index=True, default='', max_length=100, verbose_name='Артикул (MPN)'),
        ),
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('source', models.CharField(choices=[('dns', 'DNS'), ('ozon', 'Ozon'), ('citilink', 'Ситилинк')], db_index=True, max_length=32, verbose_name='Магазин')),
                ('url', models.URLField(max_length=1024, verbose_name='URL оффера')),
                ('vendor_code', models.CharField(blank=True, db_index=True, default='', max_length=128, verbose_name='Артикул в магазине')),
                ('image_url', models.URLField(blank=True, default='', max_length=1024, verbose_name='Картинка оффера')),
                ('is_available', models.BooleanField(default=True, verbose_name='В наличии')),
                ('last_seen_at', models.DateTimeField(blank=True, null=True, verbose_name='Последний успешный парсинг')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offers', to='products.product', verbose_name='Мастер-товар')),
            ],
            options={
                'verbose_name': 'Оффер',
                'verbose_name_plural': 'Офферы',
                'ordering': ['source', '-last_seen_at'],
                'indexes': [models.Index(fields=['product', 'source'], name='products_of_product_e83039_idx')],
                'constraints': [models.UniqueConstraint(fields=('source', 'url'), name='offer_source_url_unique')],
            },
        ),
    ]
