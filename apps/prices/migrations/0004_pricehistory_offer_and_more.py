

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prices', '0003_alter_pricehistory_source_citilink'),
        ('products', '0004_alter_product_vendor_code_offer'),
    ]

    operations = [
        migrations.AddField(
            model_name='pricehistory',
            name='offer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='price_history', to='products.offer', verbose_name='Оффер'),
        ),
        migrations.AddIndex(
            model_name='pricehistory',
            index=models.Index(fields=['offer', '-timestamp'], name='prices_pric_offer_i_f161d6_idx'),
        ),
        migrations.AddIndex(
            model_name='pricehistory',
            index=models.Index(fields=['product', 'source', 'is_actual'], name='prices_pric_product_e200b9_idx'),
        ),
    ]
