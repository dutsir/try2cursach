"""Management command to set up and verify TimescaleDB configuration."""
import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Set up and verify TimescaleDB hypertable, compression, and retention policies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Only check status without making changes',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset policies and recreate (careful: requires downtime)',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        check_only = options.get('check', False)
        reset = options.get('reset', False)

        try:
            self._verify_timescaledb_extension()
            self.stdout.write(self.style.SUCCESS('✓ TimescaleDB extension installed'))
        except CommandError as e:
            self.stdout.write(self.style.ERROR(f'✗ {e}'))
            return

        table_name = 'prices_pricehistory'

        # Check if table is a hypertable
        is_hypertable = self._check_hypertable(table_name)
        if is_hypertable:
            self.stdout.write(self.style.SUCCESS(f'✓ {table_name} is a hypertable'))
        else:
            if check_only:
                self.stdout.write(self.style.WARNING(f'⚠ {table_name} is NOT a hypertable'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ {table_name} is not a hypertable, creating...'))
                self._create_hypertable(table_name)
                self.stdout.write(self.style.SUCCESS(f'✓ Created hypertable {table_name}'))

        # Check compression policy
        compression_exists = self._check_compression_policy(table_name)
        if compression_exists:
            self.stdout.write(self.style.SUCCESS(f'✓ Compression policy exists'))
        else:
            if check_only:
                self.stdout.write(self.style.WARNING(f'⚠ Compression policy not found'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Adding compression policy...'))
                self._add_compression_policy(table_name)
                self.stdout.write(self.style.SUCCESS(f'✓ Added compression policy'))

        # Check retention policy
        retention_exists = self._check_retention_policy(table_name)
        if retention_exists:
            self.stdout.write(self.style.SUCCESS(f'✓ Retention policy exists'))
        else:
            if check_only:
                self.stdout.write(self.style.WARNING(f'⚠ Retention policy not found'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Adding retention policy...'))
                self._add_retention_policy(table_name)
                self.stdout.write(self.style.SUCCESS(f'✓ Added retention policy'))

        # Show table stats
        stats = self._get_table_stats(table_name)
        self.stdout.write('\n' + self.style.HTTP_INFO('Table Statistics:'))
        self.stdout.write(f'  Chunks: {stats["chunk_count"]}')
        self.stdout.write(f'  Compressed chunks: {stats["compressed_count"]}')
        self.stdout.write(f'  Total rows: {stats["row_count"]:,}')
        self.stdout.write(f'  Size: {stats["size_mb"]:.2f} MB')

        if check_only:
            self.stdout.write('\n' + self.style.HTTP_INFO('(Check-only mode; no changes made)'))

    def _verify_timescaledb_extension(self):
        """Verify that TimescaleDB extension is installed."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
            if not cursor.fetchone():
                raise CommandError(
                    'TimescaleDB extension not found. Install with: CREATE EXTENSION IF NOT EXISTS timescaledb'
                )

    def _check_hypertable(self, table_name: str) -> bool:
        """Check if table is already a hypertable."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM timescaledb_information.hypertables
                    WHERE table_name = %s
                )
            """, [table_name])
            return cursor.fetchone()[0]

    def _create_hypertable(self, table_name: str):
        """Create hypertable on timestamp column."""
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT create_hypertable(
                    '{table_name}',
                    'timestamp',
                    chunk_time_interval => INTERVAL '1 month',
                    if_not_exists => true
                )
            """)

    def _check_compression_policy(self, table_name: str) -> bool:
        """Check if compression policy exists."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM timescaledb_information.compression_settings
                    WHERE hypertable_name = %s
                )
            """, [table_name])
            return cursor.fetchone()[0]

    def _add_compression_policy(self, table_name: str):
        """Add compression policy for chunks >30 days old."""
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT add_compression_policy(
                    '{table_name}',
                    INTERVAL '30 days',
                    if_not_exists => true
                )
            """)

    def _check_retention_policy(self, table_name: str) -> bool:
        """Check if retention policy exists."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM timescaledb_information.jobs
                    WHERE proc_name = 'policy_retention'
                    AND hypertable_name = %s
                )
            """, [table_name])
            return cursor.fetchone()[0]

    def _add_retention_policy(self, table_name: str):
        """Add retention policy to drop data >1 year old."""
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT add_retention_policy(
                    '{table_name}',
                    INTERVAL '1 year',
                    if_not_exists => true
                )
            """)

    def _get_table_stats(self, table_name: str) -> dict:
        """Get table statistics."""
        stats = {
            'chunk_count': 0,
            'compressed_count': 0,
            'row_count': 0,
            'size_mb': 0.0,
        }

        with connection.cursor() as cursor:
            # Get chunk count
            cursor.execute("""
                SELECT COUNT(*) FROM timescaledb_information.chunks
                WHERE hypertable_name = %s
            """, [table_name])
            stats['chunk_count'] = cursor.fetchone()[0]

            # Get compressed chunk count
            cursor.execute("""
                SELECT COUNT(*) FROM timescaledb_information.chunks
                WHERE hypertable_name = %s AND is_compressed = true
            """, [table_name])
            stats['compressed_count'] = cursor.fetchone()[0]

            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            stats['row_count'] = cursor.fetchone()[0]

            # Get table size
            cursor.execute(f"""
                SELECT pg_total_relation_size('{table_name}') / (1024.0 * 1024.0)
            """)
            stats['size_mb'] = cursor.fetchone()[0]

        return stats
