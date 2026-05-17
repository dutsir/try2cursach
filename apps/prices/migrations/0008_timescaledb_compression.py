# Generated migration for TimescaleDB compression policy
from django.db import migrations


def add_compression_policy(apps, schema_editor):
    """Add compression policy for chunks older than 30 days."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT add_compression_policy(
                'prices_pricehistory',
                INTERVAL '30 days',
                if_not_exists => true
            );
        """)

        cursor.execute("""
            ALTER TABLE prices_pricehistory SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'product_id, source, timestamp DESC'
            );
        """)


def remove_compression_policy(apps, schema_editor):
    """Remove compression policy (rollback)."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT remove_compression_policy(
                'prices_pricehistory',
                if_exists => true
            );
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('prices', '0007_timescaledb_hypertable'),
    ]

    operations = [
        migrations.RunPython(add_compression_policy, remove_compression_policy),
    ]
