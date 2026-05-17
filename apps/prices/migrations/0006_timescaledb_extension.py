# Generated migration to install TimescaleDB extension
from django.db import migrations


def install_extension(apps, schema_editor):
    """Install TimescaleDB extension if not already installed."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")


def uninstall_extension(apps, schema_editor):
    """Uninstall TimescaleDB extension (rollback)."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP EXTENSION IF NOT EXISTS timescaledb CASCADE")


class Migration(migrations.Migration):

    dependencies = [
        ('prices', '0005_parserun'),
    ]

    operations = [
        migrations.RunPython(install_extension, uninstall_extension),
    ]
