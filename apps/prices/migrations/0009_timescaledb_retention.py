# Generated migration for TimescaleDB retention policy
import logging
from django.db import migrations

logger = logging.getLogger(__name__)


def add_retention_policy(apps, schema_editor):
    """Add retention policy to drop data older than 1 year."""
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT add_retention_policy(
                    'prices_pricehistory',
                    INTERVAL '1 year',
                    if_not_exists => true
                );
            """)
        except Exception as e:
            logger.warning(
                f"Failed to add retention policy (TimescaleDB not available): {e}. "
                "Retention policy requires TimescaleDB in production."
            )


def remove_retention_policy(apps, schema_editor):
    """Remove retention policy (rollback)."""
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT remove_retention_policy(
                    'prices_pricehistory',
                    if_not_exists => true
                );
            """)
        except Exception:
            pass  # Policy doesn't exist


class Migration(migrations.Migration):

    dependencies = [
        ('prices', '0008_timescaledb_compression'),
    ]

    operations = [
        migrations.RunPython(add_retention_policy, remove_retention_policy),
    ]
