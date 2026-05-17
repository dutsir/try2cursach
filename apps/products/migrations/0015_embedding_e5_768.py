from django.db import migrations
from pgvector.django import HnswIndex, VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0014_swap_embedding_and_hnsw_index'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='product',
            name='product_match_embedding_hnsw',
        ),
        migrations.RunSQL(
            sql='UPDATE products_product SET match_embedding = NULL WHERE match_embedding IS NOT NULL;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='product',
            name='match_embedding',
            field=VectorField(
                dimensions=768,
                null=True,
                blank=True,
                verbose_name='Embedding для матчинга',
                help_text='Вектор sentence-transformers для cross-source semantic match',
            ),
        ),
        migrations.AddIndex(
            model_name='product',
            index=HnswIndex(
                name='product_match_embedding_hnsw',
                fields=['match_embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ),
    ]
