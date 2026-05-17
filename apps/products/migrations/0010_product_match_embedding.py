from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_product_specs_fingerprint_gin'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='match_embedding',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='L2-normalized vector для semantic match (sentence-transformers)',
                verbose_name='Embedding для матчинга',
            ),
        ),
    ]
