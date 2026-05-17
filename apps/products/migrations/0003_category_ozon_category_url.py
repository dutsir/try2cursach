

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_category_citilink_and_product_url_verbose'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='ozon_category_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Полный URL раздела Ozon, например https://www.ozon.ru/category/noutbuki-15692/',
                max_length=1024,
                verbose_name='URL категории Ozon',
            ),
        ),
    ]
