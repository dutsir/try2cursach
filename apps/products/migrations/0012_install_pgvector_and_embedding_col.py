from django.db import migrations
from pgvector.django import VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_offer_mpn_index'),
    ]

    operations = [
        migrations.RunSQL(
            sql='CREATE EXTENSION IF NOT EXISTS vector;',


            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddField(
            model_name='product',
            name='match_embedding_vec',
            field=VectorField(
                dimensions=384,
                null=True,
                blank=True,
                verbose_name='Embedding для матчинга (vector)',
            ),
        ),
    ]
