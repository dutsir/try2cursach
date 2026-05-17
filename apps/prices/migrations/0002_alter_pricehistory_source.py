

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prices', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pricehistory',
            name='source',
            field=models.CharField(choices=[('dns', 'DNS'), ('ozon', 'Ozon')], default='dns', max_length=50, verbose_name='Источник'),
        ),
    ]
