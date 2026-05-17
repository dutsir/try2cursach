from django.db import migrations, models
from pgvector.django import HnswIndex, VectorField


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0013_backfill_embedding_vec'),
    ]

    operations = [

        migrations.RemoveField(
            model_name='product',
            name='match_embedding',
        ),


        migrations.RenameField(
            model_name='product',
            old_name='match_embedding_vec',
            new_name='match_embedding',
        ),

        migrations.AlterField(
            model_name='product',
            name='match_embedding',
            field=VectorField(
                dimensions=384,
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
