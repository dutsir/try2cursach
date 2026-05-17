

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='citilink_catalog_path',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Пример: catalog/noutbuki-118346/ или https://www.citilink.ru/catalog/...',
                max_length=1024,
                verbose_name='Каталог Ситилинк (путь или полный URL)',
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='url',
            field=models.URLField(max_length=1024, verbose_name='URL карточки товара'),
        ),
    ]
