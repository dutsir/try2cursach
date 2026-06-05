from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.test import override_settings

from apps.products.dedupe.matcher import (
    _auto_identity_guard,
    block_candidates,
    find_master,
    hard_reject,
    score,
)
from apps.products.dedupe.normalizer import normalize_offer
from apps.products.dedupe.services import upsert_offer
from apps.products.models import Category, MatchReview, Offer, Product

FIXTURE = Path(__file__).parent / 'fixtures' / 'golden_pairs.json'


def _ensure_category(slug: str) -> Category:
    cat, _ = Category.objects.get_or_create(
        slug=slug,
        defaults={'name': slug.replace('-', ' ').title()},
    )
    return cat


def _upsert(case_payload: dict) -> Offer:
    cat = _ensure_category(case_payload['category'])
    res = upsert_offer(
        category=cat,
        source=case_payload['source'],
        name=case_payload['name'],
        url=case_payload['url'],
        vendor_code=case_payload.get('sku', ''),
    )
    return res.offer


@pytest.fixture(scope='module')
def golden() -> dict:
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


@pytest.mark.django_db
class TestMustMerge:
    @pytest.mark.parametrize(
        'case_id', [
            'lenovo_thinkpad_e16_g2_dns_citilink',
            'macbook_pro_mkgt3rua',
            'asus_vivobook_mpn_match_dns_citilink',
            'huawei_matebook_d16_dns_citilink',
            'rtx_4070_palit_mpn_match',
            'rtx_5070_msi_gaming_trio',
        ],
    )
    def test_pair_merges(self, case_id, golden):
        case = next(c for c in golden['must_merge'] if c['id'] == case_id)
        offer_a = _upsert(case['a'])
        offer_b = _upsert(case['b'])
        assert offer_a.product_id == offer_b.product_id, (
            f'{case_id}: ожидался один Product, получили '
            f'{offer_a.product_id} != {offer_b.product_id}'
        )


@pytest.mark.django_db
class TestMustNotMerge:
    @pytest.mark.parametrize(
        'case_id', [
            'thinkpad_e16_diff_ram',
            'matebook_d_diff_diagonal',
            'vivobook_mpn_au982_vs_au111',
            'rtx_4070_vs_rtx_4060',
            'thinkpad_diff_storage',
            'wrong_brand',
            'different_categories',
        ],
    )
    def test_pair_not_merged(self, case_id, golden):
        case = next(c for c in golden['must_not_merge'] if c['id'] == case_id)
        offer_a = _upsert(case['a'])
        offer_b = _upsert(case['b'])
        assert offer_a.product_id != offer_b.product_id, (
            f'{case_id}: товары слиплись, хотя должны быть разделены'
        )


@pytest.mark.django_db
class TestMustReview:
    @pytest.mark.parametrize(
        'case_id', [
            'ozon_dns_v3607vm_no_mpn',
            'huawei_matebook_d16_specs_match_no_mpn',
            'ozon_thinkpad_no_mpn',
        ],
    )
    def test_review_queue(self, case_id, golden):
        case = next(c for c in golden['must_review'] if c['id'] == case_id)


        if case['a']['source'] == 'ozon' and case['b']['source'] == 'dns':
            strong, weak = case['b'], case['a']
        else:
            strong, weak = case['a'], case['b']
        strong_offer = _upsert(strong)
        weak_offer = _upsert(weak)
        if weak_offer.product_id == strong_offer.product_id:
            return
        assert MatchReview.objects.filter(offer=weak_offer).exists() or (
            weak_offer.match_signals or {}
        ).get('decision') in {'review', 'new'}


@pytest.mark.django_db
class TestMatcherProperties:
    def test_score_self(self):
        cat = _ensure_category('property-test')


        name = 'Lenovo ThinkPad E16 G2 21M6S1F000_32G 16" 32GB DDR5 1TB SSD Core 7'
        f = normalize_offer(
            name=name, source='dns', category_id=cat.pk,
            sku='21M6S1F000_32G', url='',
        )
        from apps.products.dedupe.services import _features_to_product

        p, _created = _features_to_product(
            f, name=name, image_url='', fallback_url='', category=cat,
        )
        s, sig = score(p, f)
        assert s >= 0.9, (s, sig)

    def test_hard_reject_brand_mismatch(self):
        cat = _ensure_category('property-test-brand')
        p = Product.objects.create(
            name='ASUS Vivobook',
            slug='asus-vivobook-test',
            category=cat,
            vendor_code='X1704VA-AU982',
            brand='asus',
        )
        f = normalize_offer(
            name='Acer Aspire X1704VA-AU982',
            source='dns', category_id=cat.pk,
            sku='', url='',
        )
        is_rej, why = hard_reject(p, f)
        assert is_rej and why == 'brand_mismatch'

    def test_hard_reject_mpn_mismatch(self):
        cat = _ensure_category('property-test-mpn')
        p = Product.objects.create(
            name='ASUS Vivobook',
            slug='asus-vivobook-test-mpn',
            category=cat,
            vendor_code='X1704VA-AU982',
            brand='asus',
        )
        f = normalize_offer(
            name='ASUS Vivobook X1704VA-AU111',
            source='dns', category_id=cat.pk,
            sku='', url='',
        )
        is_rej, why = hard_reject(p, f)
        assert is_rej and why == 'mpn_mismatch'

    def test_hard_reject_category_mismatch(self):
        cat_a = _ensure_category('cat-a')
        cat_b = _ensure_category('cat-b')
        p = Product.objects.create(
            name='ASUS', slug='asus-cat-a',
            category=cat_a, brand='asus',
        )
        f = normalize_offer(
            name='ASUS Vivobook', source='dns',
            category_id=cat_b.pk, sku='', url='',
        )
        is_rej, why = hard_reject(p, f)
        assert is_rej and why == 'category_mismatch'

    def test_block_candidates_limits(self):
        cat = _ensure_category('block-test')
        for i in range(5):
            Product.objects.create(
                name=f'ASUS Vivobook X1704VA-AU{i}',
                slug=f'asus-block-{i}',
                category=cat, brand='asus',
                vendor_code=f'X1704VA-AU{i}',
            )
        f = normalize_offer(
            name='ASUS Vivobook 17',
            source='dns', category_id=cat.pk,
            sku='', url='',
        )
        cand = block_candidates(f, category_id=cat.pk, limit=3)
        assert len(cand) <= 3

    def test_auto_identity_guard_rejects_generic_only_tokens(self):
        cat = _ensure_category('guard-generic')
        p = Product.objects.create(
            name='Внешний HDD Seagate 2TB USB 3.0',
            slug='seagate-2tb-generic',
            category=cat,
            brand='seagate',
            vendor_code='',
            url='https://example.com/p1',
        )
        f = normalize_offer(
            name='Жесткий диск Seagate 2TB USB 3.0',
            source='dns',
            category_id=cat.pk,
            sku='',
            url='https://example.com/p2',
        )
        ok, reason = _auto_identity_guard(
            product=p,
            features=f,
            raw_name='Жесткий диск Seagate 2TB USB 3.0',
            signals={'rule': 'weighted_score'},
        )
        assert ok is False
        assert reason == 'identity_tokens_too_generic'

    def test_auto_identity_guard_accepts_specific_model_token(self):
        cat = _ensure_category('guard-specific')
        p = Product.objects.create(
            name='Seagate STKY2000401 2TB',
            slug='seagate-stky2000401',
            category=cat,
            brand='seagate',
            vendor_code='',
            url='https://example.com/p3',
        )
        f = normalize_offer(
            name='Внешний HDD Seagate STKY2000401 2TB',
            source='dns',
            category_id=cat.pk,
            sku='',
            url='https://example.com/p4',
        )
        ok, reason = _auto_identity_guard(
            product=p,
            features=f,
            raw_name='Внешний HDD Seagate STKY2000401 2TB',
            signals={'rule': 'weighted_score'},
        )
        assert ok is True
        assert reason == ''

    def test_idempotent_repeat(self):
        cat = _ensure_category('idem-test')
        payload = {
            'name': 'Lenovo ThinkPad E16 G2 [21m6s1f000_32g]',
            'source': 'citilink',
            'category': 'idem-test',
            'sku': 'IDEM-001',
            'url': 'https://www.citilink.ru/product/idem-test/',
        }
        a = _upsert(payload)
        b = _upsert(payload)

        assert a.pk == b.pk

        payload2 = {**payload, 'url': payload['url'] + '?utm=foo'}
        c = _upsert(payload2)
        assert a.pk == c.pk


@pytest.mark.django_db
class TestLegacyServicesBridge:
    @override_settings(DEDUP_V2=True)
    def test_legacy_upsert_uses_v2_when_flag_on(self):
        from apps.products.services import upsert_offer as legacy_upsert

        cat = _ensure_category('bridge-test')
        res = legacy_upsert(
            category=cat,
            source='dns',
            name='Lenovo ThinkPad E16 G2 [21m6s1f000_32g]',
            url='https://www.dns-shop.ru/product/bridge-test/',
            vendor_code='21M6S1F000',
        )
        assert res.offer.product_id is not None

        assert res.offer.product.brand == 'lenovo'
        assert res.offer.product.vendor_code == '21M6S1F000_32G'

    @override_settings(DEDUP_V2=False, DEDUP_SHADOW=False)
    def test_legacy_upsert_runs_legacy(self):
        from apps.products.services import upsert_offer as legacy_upsert

        cat = _ensure_category('bridge-legacy')
        res = legacy_upsert(
            category=cat,
            source='dns',
            name='Lenovo ThinkPad E16 G2 [21m6s1f000_32g]',
            url='https://www.dns-shop.ru/product/bridge-legacy/',
            vendor_code='21M6S1F000',
        )


        assert res.offer.product_id is not None


@pytest.mark.django_db
class TestDuplicateProductGuard:
    def test_features_to_product_reuses_brand_mpn(self):
        from apps.products.dedupe.services import _features_to_product

        cat = _ensure_category('dup-mpn')
        f = normalize_offer(
            name='Honor MagicBook X16 2024 5301ALXN 16GB',
            source='ozon',
            category_id=cat.pk,
            sku='111111111',
            url='https://www.ozon.ru/product/honor-magicbook-x16-111111111/',
        )
        f.brand = 'honor'
        f.model_code = '5301ALXN'
        p1, created1 = _features_to_product(
            f,
            name='Honor MagicBook X16 2024 5301ALXN 16GB 512GB',
            image_url='',
            fallback_url='https://www.ozon.ru/product/honor-magicbook-x16-111111111/',
            category=cat,
        )
        p2, created2 = _features_to_product(
            f,
            name='Honor MagicBook X16 2024 5301ALXN 16GB 1TB',
            image_url='',
            fallback_url='https://www.ozon.ru/product/honor-magicbook-x16-222222222/',
            category=cat,
        )
        assert created1 is True
        assert created2 is False
        assert p1.pk == p2.pk
        assert Product.objects.filter(
            category=cat, brand='honor', vendor_code='5301ALXN',
        ).count() == 1
