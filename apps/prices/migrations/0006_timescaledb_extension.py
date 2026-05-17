# Generated migration to install TimescaleDB extension
import logging
from django.db import migrations

logger = logging.getLogger(__name__)


def install_extension(apps, schema_editor):
    """Install TimescaleDB extension if not already installed."""
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        except Exception as e:
            logger.warning(
                f"TimescaleDB extension not available (dev environment?): {e}. "
                "Continuing without it. Time-series compression requires TimescaleDB in production."
            )


def uninstall_extension(apps, schema_editor):
    """Uninstall TimescaleDB extension (rollback)."""
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE")
        except Exception:
            pass  # Already doesn't exist


class Migration(migrations.Migration):

    dependencies = [
        ('prices', '0005_parserun'),
    ]

    operations = [
        migrations.RunPython(install_extension, uninstall_extension),
    ]
