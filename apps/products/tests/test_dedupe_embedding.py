from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.products.dedupe.embedding import (
    build_match_text,
    cosine_similarity,
    pick_display_name,
)
from apps.products.dedupe.features import Features
from apps.products.dedupe.matcher import find_cross_source_specs_match, find_master
from apps.products.dedupe.normalizer import normalize_offer
from apps.products.models import Category, Product


def _cat(slug: str = 'emb-test') -> Category:
    c, _ = Category.objects.get_or_create(
        slug=slug,
        defaults={'name': slug, 'is_active': True},
    )
    return c


@pytest.mark.django_db
class TestCrossSourceSpecs:
    @override_settings(DEDUP_V2=True, DEDUP_CROSS_SOURCE_SPECS_ENABLED=True)
    def test_ozon_matches_dns_by_specs(self):
        cat = _cat('cross-specs')
        dns = Product.objects.create(
            name='HUAWEI MateBook D 16 MCLG-X 16" Core 5 16GB 512GB',
            slug='huawei-matebook-dns',
            category=cat,
            vendor_code='MCLG-X',
            brand='huawei',
            url='https://dns.example/p/1',
            specs_fingerprint={
                'ram_gb': 16,
                'storage_gb': 512,
                'screen_in': '16',
                'cpu_family': 'core 5',
            },
        )
        features = normalize_offer(
            name='ноутбук huawei matebook d 16 16 ddr5 16гб 512 ssd intel core 5',
            source='ozon',
            category_id=cat.pk,
            sku='12345',
            url='https://www.ozon.ru/product/matebook-12345/',
        )
        features.model_code = ''
        features.specs = {
            'ram_gb': 16,
            'storage_gb': 512,
            'screen_in': '16',
            'cpu_family': 'core 5',
        }
        result = find_cross_source_specs_match(features, category_id=cat.pk)
        assert result is not None
        assert result.product.pk == dns.pk
        assert result.decision == 'auto_merge'


@override_settings(DEDUP_EMBEDDING_MODEL='intfloat/multilingual-e5-base')
def test_e5_query_passage_prefixes():
    f = Features(brand='asus', clean_name='noutbuk vivobook', specs={'ram_gb': 16})
    assert build_match_text(f, role='query').startswith('query:')
    assert build_match_text(f, role='passage').startswith('passage:')


def test_pick_display_name_prefers_cyrillic():
    assert pick_display_name(
        'noutbuk asus vivobook',
        'Ноутбук ASUS VivoBook 15',
    ) == 'Ноутбук ASUS VivoBook 15'


@pytest.mark.django_db
class TestEmbeddingMatch:
    @override_settings(DEDUP_V2=True, DEDUP_EMBEDDING_ENABLED=True)
    @patch('apps.products.dedupe.matcher._try_embedding_match')
    def test_embedding_auto_merge(self, mock_emb):
        from apps.products.dedupe.matcher import MatchResult

        cat = _cat('emb-match')


        master = Product.objects.create(
            name='ASUS V3607VM-RP090 16 Core 5',
            slug='asus-v3607-master',
            category=cat,
            vendor_code='V3607VM-RP090',
            brand='asus',
            url='https://dns.example/p/2',
            specs_fingerprint={'ram_gb': 16, 'storage_gb': 512},
        )
        mock_emb.return_value = MatchResult(
            master, 0.91, {'rule': 'embedding', 'similarity': 0.91}, 'auto_merge',
        )

        features = normalize_offer(
            name='asus v3607vm rp090 noutbuk 16 intel core 5',
            source='ozon',
            category_id=cat.pk,
            sku='999',
            url='https://www.ozon.ru/product/asus-v3607vm-999/',
        )
        features.model_code = ''
        result = find_master(features, category_id=cat.pk, raw_name=features.clean_name)
        assert result.decision == 'auto_merge'
        assert result.product.pk == master.pk
        assert result.signals.get('rule') == 'embedding'


def test_cosine_identical():
    v = [0.6, 0.8]
    assert cosine_similarity(v, v) == pytest.approx(1.0, abs=0.01)
