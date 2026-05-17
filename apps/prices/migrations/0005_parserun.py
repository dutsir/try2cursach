

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prices', '0004_pricehistory_offer_and_more'),
        ('products', '0004_alter_product_vendor_code_offer'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParseRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('source', models.CharField(choices=[('dns', 'DNS'), ('ozon', 'Ozon'), ('citilink', 'Ситилинк')], db_index=True, max_length=32, verbose_name='Источник')),
                ('status', models.CharField(choices=[('running', 'Идёт'), ('ok', 'Успех'), ('empty', 'Пусто'), ('error', 'Ошибка')], db_index=True, default='running', max_length=16, verbose_name='Статус')),
                ('started_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Начало')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='Конец')),
                ('parsed_count', models.PositiveIntegerField(default=0, verbose_name='Карточек спарсено')),
                ('saved_offers', models.PositiveIntegerField(default=0, verbose_name='Офферов сохранено')),
                ('new_offers', models.PositiveIntegerField(default=0, verbose_name='Новых офферов')),
                ('new_products', models.PositiveIntegerField(default=0, verbose_name='Новых мастер-товаров')),
                ('saved_prices', models.PositiveIntegerField(default=0, verbose_name='Новых записей цен')),
                ('error_message', models.TextField(blank=True, default='', verbose_name='Ошибка')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='parse_runs', to='products.category', verbose_name='Категория')),
            ],
            options={
                'verbose_name': 'Прогон парсера',
                'verbose_name_plural': 'Прогоны парсеров',
                'ordering': ['-started_at'],
                'indexes': [models.Index(fields=['source', '-started_at'], name='prices_pars_source_0eb2ae_idx')],
            },
        ),
    ]
