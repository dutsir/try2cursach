"""Tests for embedding training data extraction and preparation."""
from decimal import Decimal
from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.products.models import Category, Product, Offer, MergeAuditLog
from apps.products.dedupe.training_data import (
    export_merge_audit_pairs,
    split_train_test,
    TrainingPair,
)


class TrainingDataExportTest(TestCase):
    """Test training data extraction from MergeAuditLog."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name='Test', slug='test')

        # Create master products
        self.product1 = Product.objects.create(
            name='Intel Core i9-14900K',
            slug='intel-core-i9-14900k',
            category=self.category,
            brand='Intel',
            vendor_code='i9-14900k',
            url='https://example.com/product1',
        )

        self.product2 = Product.objects.create(
            name='Different Product',
            slug='different-product',
            category=self.category,
            brand='AMD',
            url='https://example.com/product2',
        )

        # Create offers from different sources
        self.offer_dns = Offer.objects.create(
            product=self.product1,
            source='dns',
            url='https://dns.ru/product1',
            raw_name='Intel Core i9-14900K',
            vendor_code='i9-14900k',
        )

        self.offer_ozon = Offer.objects.create(
            product=self.product1,
            source='ozon',
            url='https://ozon.ru/product1',
            raw_name='Intel Core i9 14900K',
            vendor_code='i9-14900k',
        )

        self.offer_citilink = Offer.objects.create(
            product=self.product1,
            source='citilink',
            url='https://citilink.ru/product1',
            raw_name='Core i9-14900K',
            vendor_code='i9-14900k',
        )

    def test_export_empty_audit_log(self):
        """Test exporting from empty audit log."""
        pairs = export_merge_audit_pairs(max_pairs=10)
        self.assertEqual(len(pairs), 0, 'Expected no pairs from empty audit log')

    def test_export_auto_merge_pairs(self):
        """Test exporting positive pairs from auto-merge decisions."""
        # Create auto-merge decisions
        log1 = MergeAuditLog.objects.create(
            offer=self.offer_dns,
            to_product=self.product1,
            actor=MergeAuditLog.Actor.AUTO,
            decision=MergeAuditLog.Decision.AUTO_MERGE,
            score=Decimal('0.95'),
        )

        log2 = MergeAuditLog.objects.create(
            offer=self.offer_ozon,
            to_product=self.product1,
            actor=MergeAuditLog.Actor.AUTO,
            decision=MergeAuditLog.Decision.AUTO_MERGE,
            score=Decimal('0.92'),
        )

        pairs = export_merge_audit_pairs()

        # Should create cross-source pairs (DNS<>OZON, DNS<>Citilink, OZON<>Citilink)
        positive_pairs = [p for p in pairs if p.label == 1]
        self.assertGreater(len(positive_pairs), 0, 'No positive pairs found')

        # Verify pair properties
        for pair in positive_pairs:
            self.assertIn(pair.offer_a_source, ['dns', 'ozon', 'citilink'])
            self.assertIn(pair.offer_b_source, ['dns', 'ozon', 'citilink'])
            self.assertNotEqual(pair.offer_a_source, pair.offer_b_source)
            self.assertEqual(pair.label, 1)
            self.assertGreater(pair.score, 0)

    def test_export_hard_reject_pairs(self):
        """Test exporting negative pairs from hard rejects."""
        # Create a rejected decision
        log = MergeAuditLog.objects.create(
            offer=self.offer_ozon,
            from_product=self.product1,
            actor=MergeAuditLog.Actor.AUTO,
            decision=MergeAuditLog.Decision.NEW,
            signals={'rejected': 'brand_mismatch'},
        )

        pairs = export_merge_audit_pairs()

        negative_pairs = [p for p in pairs if p.label == 0]
        self.assertGreater(len(negative_pairs), 0, 'No negative pairs found')

        for pair in negative_pairs:
            self.assertEqual(pair.label, 0)
            self.assertEqual(pair.score, 0.0)

    def test_training_pair_structure(self):
        """Test TrainingPair dataclass structure."""
        pair = TrainingPair(
            offer_a_name='Intel Core i9',
            offer_b_name='i9-14900K',
            offer_a_specs='Intel | CPU | 24 cores',
            offer_b_specs='Intel | CPU | 24 cores',
            offer_a_source='dns',
            offer_b_source='ozon',
            label=1,
            score=0.95,
            score_confidence='high',
        )

        self.assertEqual(pair.label, 1)
        self.assertEqual(pair.score, 0.95)
        self.assertEqual(pair.offer_a_source, 'dns')

        # Test conversion to dict
        d = pair.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d['label'], 1)


class TrainTestSplitTest(TestCase):
    """Test train/val/test splitting."""

    def setUp(self):
        """Create test pairs."""
        self.pairs = [
            TrainingPair(
                offer_a_name='Product A',
                offer_b_name='Product B',
                offer_a_specs='Spec A',
                offer_b_specs='Spec B',
                offer_a_source='dns',
                offer_b_source='ozon',
                label=1,
                score=0.9,
                score_confidence='high',
            )
            for _ in range(100)
        ]

    def test_split_proportions(self):
        """Test that split maintains correct proportions."""
        train, val, test = split_train_test(
            self.pairs,
            train_ratio=0.8,
            val_ratio=0.1,
        )

        total = len(train) + len(val) + len(test)
        self.assertEqual(total, 100)
        self.assertAlmostEqual(len(train) / total, 0.8, places=1)
        self.assertAlmostEqual(len(val) / total, 0.1, places=1)
        self.assertAlmostEqual(len(test) / total, 0.1, places=1)

    def test_split_stratification(self):
        """Test that split stratifies by label."""
        # Create mixed labels
        mixed_pairs = (
            [TrainingPair(
                offer_a_name='A', offer_b_name='B',
                offer_a_specs='S1', offer_b_specs='S2',
                offer_a_source='dns', offer_b_source='ozon',
                label=1, score=0.9, score_confidence='high'
            ) for _ in range(50)] +
            [TrainingPair(
                offer_a_name='C', offer_b_name='D',
                offer_a_specs='S3', offer_b_specs='S4',
                offer_a_source='dns', offer_b_source='ozon',
                label=0, score=0.1, score_confidence='high'
            ) for _ in range(50)]
        )

        train, val, test = split_train_test(
            mixed_pairs,
            train_ratio=0.8,
            val_ratio=0.1,
        )

        # Check that each set has both positive and negative labels
        train_labels = set(p.label for p in train)
        val_labels = set(p.label for p in val)
        test_labels = set(p.label for p in test)

        self.assertEqual(train_labels, {0, 1})
        self.assertEqual(val_labels, {0, 1})
        self.assertEqual(test_labels, {0, 1})

    def test_split_no_overlap(self):
        """Test that splits don't overlap."""
        train, val, test = split_train_test(self.pairs)

        train_ids = {id(p) for p in train}
        val_ids = {id(p) for p in val}
        test_ids = {id(p) for p in test}

        # Since we're splitting the same list, check no overlap in indices
        self.assertEqual(len(train_ids & val_ids), 0)
        self.assertEqual(len(train_ids & test_ids), 0)
        self.assertEqual(len(val_ids & test_ids), 0)
