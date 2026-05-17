

import django.contrib.postgres.indexes
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_dedupe_v2_schema'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='product',
            index=django.contrib.postgres.indexes.GinIndex(fields=['specs_fingerprint'], name='product_specs_fingerprint_gin'),
        ),
    ]
