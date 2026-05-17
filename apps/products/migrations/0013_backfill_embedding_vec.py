from __future__ import annotations

from django.db import migrations

_BATCH = 500
_EXPECTED_DIM = 384


def copy_embeddings(apps, schema_editor):
    Product = apps.get_model('products', 'Product')


    qs = (
        Product.objects
        .exclude(match_embedding__isnull=True)
        .exclude(match_embedding=[])
        .order_by('pk')
    )
    total = qs.count()
    if not total:
        return

    copied = 0
    skipped_dim = 0
    last_pk = 0
    while True:
        chunk = list(qs.filter(pk__gt=last_pk)[:_BATCH])
        if not chunk:
            break
        to_update = []
        for p in chunk:
            emb = p.match_embedding
            if not isinstance(emb, list) or len(emb) != _EXPECTED_DIM:
                skipped_dim += 1
                continue

            p.match_embedding_vec = emb
            to_update.append(p)
        if to_update:
            Product.objects.bulk_update(to_update, ['match_embedding_vec'])
            copied += len(to_update)
        last_pk = chunk[-1].pk

    schema_editor.connection.cursor().execute('SELECT 1;')
    if skipped_dim:
        print(
            f'[0013_backfill_embedding_vec] WARN: пропущено {skipped_dim} '
            f'строк с неверной размерностью (ожидалось {_EXPECTED_DIM}).'
        )
    print(
        f'[0013_backfill_embedding_vec] Скопировано {copied}/{total} '
        f'embedding-ов в match_embedding_vec.'
    )


def noop(apps, schema_editor):

    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0012_install_pgvector_and_embedding_col'),
    ]

    operations = [
        migrations.RunPython(copy_embeddings, reverse_code=noop),
    ]
