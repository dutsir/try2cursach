"""Tests for TimescaleDB hypertable setup and functionality."""
import time
from decimal import Decimal
from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone
from django.db import connection

from apps.products.models import Category, Product
from apps.prices.models import PriceHistory


class TimescaleDBSetupTest(TestCase):
    """Test TimescaleDB hypertable, compression, and retention setup."""

    def test_timescaledb_extension_installed(self):
        """Verify TimescaleDB extension is installed."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
            result = cursor.fetchone()
            self.assertIsNotNone(result, 'TimescaleDB extension not installed')

    def test_pricehistory_is_hypertable(self):
        """Verify prices_pricehistory table is a hypertable."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM timescaledb_information.hypertables
                    WHERE table_name = 'prices_pricehistory'
                )
            """)
            is_hypertable = cursor.fetchone()[0]
            self.assertTrue(is_hypertable, 'PriceHistory table is not a hypertable')

    def test_hypertable_partitioned_by_timestamp(self):
        """Verify hypertable is partitioned on timestamp column."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT time_column_name FROM timescaledb_information.hypertables
                WHERE table_name = 'prices_pricehistory'
            """)
            time_column = cursor.fetchone()[0]
            self.assertEqual(time_column, 'timestamp', 'Hypertable not partitioned on timestamp')

    def test_compression_policy_exists(self):
        """Verify compression policy is configured."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM timescaledb_information.compression_settings
                    WHERE hypertable_name = 'prices_pricehistory'
                )
            """)
            has_compression = cursor.fetchone()[0]
            self.assertTrue(has_compression, 'Compression policy not found')

    def test_retention_policy_exists(self):
        """Verify retention policy is configured."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM timescaledb_information.jobs
                    WHERE proc_name = 'policy_retention'
                    AND hypertable_name = 'prices_pricehistory'
                )
            """)
            has_retention = cursor.fetchone()[0]
            self.assertTrue(has_retention, 'Retention policy not found')


class PriceHistoryTimeSeriesTest(TestCase):
    """Test TimescaleDB time-series functionality with PriceHistory."""

    def setUp(self):
        """Create test data."""
        self.category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            category=self.category,
            url='https://example.com',
        )

    def test_insert_price_records(self):
        """Verify prices can be inserted into hypertable."""
        now = timezone.now()
        prices = [
            PriceHistory(
                product=self.product,
                price=Decimal('100.00'),
                timestamp=now - timedelta(days=i),
                source='dns',
            )
            for i in range(10)
        ]
        PriceHistory.objects.bulk_create(prices)

        count = PriceHistory.objects.filter(product=self.product).count()
        self.assertEqual(count, 10, 'Price records not inserted correctly')

    def test_timestamp_index_query_performance(self):
        """Test that timestamp index provides efficient queries."""
        now = timezone.now()

        # Insert 1000 price records
        prices = [
            PriceHistory(
                product=self.product,
                price=Decimal(f'{100 + (i % 50):0.2f}'),
                timestamp=now - timedelta(hours=i),
                source='dns',
            )
            for i in range(1000)
        ]
        PriceHistory.objects.bulk_create(prices)

        # Query by timestamp range (should use index)
        start_time = now - timedelta(days=7)
        end_time = now

        t0 = time.time()
        recent_prices = PriceHistory.objects.filter(
            product=self.product,
            timestamp__gte=start_time,
            timestamp__lte=end_time,
        )
        execution_time = time.time() - t0

        # Should execute quickly with index (~<100ms)
        self.assertLess(execution_time, 0.5, f'Query too slow: {execution_time:.3f}s')
        self.assertGreater(recent_prices.count(), 0, 'No recent prices found')

    def test_order_by_timestamp(self):
        """Test ordering by timestamp works correctly."""
        now = timezone.now()

        # Insert prices in random order
        import random
        hours = list(range(10))
        random.shuffle(hours)

        prices = [
            PriceHistory(
                product=self.product,
                price=Decimal('100.00'),
                timestamp=now - timedelta(hours=h),
                source='dns',
            )
            for h in hours
        ]
        PriceHistory.objects.bulk_create(prices)

        # Query and verify order
        ordered = PriceHistory.objects.filter(product=self.product).order_by('-timestamp')
        timestamps = [p.timestamp for p in ordered]

        # Verify descending order
        for i in range(len(timestamps) - 1):
            self.assertGreater(
                timestamps[i], timestamps[i + 1],
                'Timestamps not in descending order'
            )

    def test_filter_by_source_and_timestamp(self):
        """Test filtering by both source and timestamp."""
        now = timezone.now()

        # Insert prices from different sources
        prices = []
        for source in ['dns', 'ozon', 'citilink']:
            for i in range(5):
                prices.append(
                    PriceHistory(
                        product=self.product,
                        price=Decimal('100.00'),
                        timestamp=now - timedelta(hours=i),
                        source=source,
                    )
                )
        PriceHistory.objects.bulk_create(prices)

        # Query DNS prices from last 48 hours
        two_days_ago = now - timedelta(days=2)
        dns_recent = PriceHistory.objects.filter(
            product=self.product,
            source='dns',
            timestamp__gte=two_days_ago,
        )

        self.assertEqual(dns_recent.count(), 5, 'Incorrect filter results')
        self.assertTrue(
            all(p.source == 'dns' for p in dns_recent),
            'Non-DNS records in filtered results'
        )

    def test_chunk_creation(self):
        """Verify chunks are created for different time periods."""
        now = timezone.now()

        # Insert prices spanning multiple months
        prices = [
            PriceHistory(
                product=self.product,
                price=Decimal('100.00'),
                timestamp=now - timedelta(days=d),
                source='dns',
            )
            for d in range(0, 120, 10)  # 4 months of data
        ]
        PriceHistory.objects.bulk_create(prices)

        # Check chunk count
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM timescaledb_information.chunks
                WHERE hypertable_name = 'prices_pricehistory'
            """)
            chunk_count = cursor.fetchone()[0]

            # Should have multiple chunks (one per month)
            self.assertGreaterEqual(chunk_count, 2, 'Expected multiple chunks')

    def test_aggregation_on_time_range(self):
        """Test aggregation queries on time-series data."""
        now = timezone.now()

        # Insert varying prices
        prices = [
            PriceHistory(
                product=self.product,
                price=Decimal('100.00') + Decimal(str(i * 10)),
                timestamp=now - timedelta(hours=i),
                source='dns',
            )
            for i in range(30)
        ]
        PriceHistory.objects.bulk_create(prices)

        # Calculate average price over 7 days
        from django.db.models import Avg, Min, Max
        stats = PriceHistory.objects.filter(
            product=self.product,
            timestamp__gte=now - timedelta(days=7),
        ).aggregate(
            avg_price=Avg('price'),
            min_price=Min('price'),
            max_price=Max('price'),
        )

        self.assertIsNotNone(stats['avg_price'], 'No average price calculated')
        self.assertIsNotNone(stats['min_price'], 'No min price calculated')
        self.assertIsNotNone(stats['max_price'], 'No max price calculated')
        self.assertLess(stats['min_price'], stats['max_price'], 'Invalid price range')
