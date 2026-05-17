

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_product_match_embedding'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='offer',
            index=models.Index(
                fields=['source', 'mpn_extracted'],
                name='offer_source_mpn_idx',
            ),
        ),
    ]
