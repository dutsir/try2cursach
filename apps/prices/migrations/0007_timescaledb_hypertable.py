# Generated migration to create TimescaleDB hypertable
from django.db import migrations


def create_hypertable(apps, schema_editor):
    """Create TimescaleDB hypertable on prices_pricehistory table."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT create_hypertable(
                'prices_pricehistory',
                'timestamp',
                chunk_time_interval => INTERVAL '1 month',
                if_not_exists => true
            );
        """)


def drop_hypertable(apps, schema_editor):
    """Drop TimescaleDB hypertable (rollback)."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT drop_hypertable(
                'prices_pricehistory',
                if_exists => true,
                cascade => true
            );
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('prices', '0006_timescaledb_extension'),
    ]

    operations = [
        migrations.RunPython(create_hypertable, drop_hypertable),
    ]
