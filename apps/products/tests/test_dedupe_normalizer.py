from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.products.dedupe.normalizer import (
    dice,
    extract_brand,
    extract_mpn,
    extract_specs,
    extract_variant_from_url,
    normalize_offer,
    normalize_offer_url,
    specs_contradict,
)

FIXTURE = Path(__file__).parent / 'fixtures' / 'golden_pairs.json'


@pytest.fixture(scope='module')
def golden() -> dict:
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class TestExtractBrand:
    def test_basic_latin(self):
        assert extract_brand('ASUS Vivobook 17') == 'asus'

    def test_lowercase(self):
        assert extract_brand('asus rog strix') == 'asus'

    def test_cyrillic_alias(self):
        assert extract_brand('Леново ThinkPad') == 'lenovo'

    def test_apple(self):
        assert extract_brand('Apple MacBook Pro 16') == 'apple'

    def test_no_brand(self):
        assert extract_brand('что-то без бренда') == ''

    def test_multiword_brand_priority(self):
        assert extract_brand('Fractal Design Define 7') == 'fractal design'

    def test_punctuation_brand(self):
        assert extract_brand('Be Quiet! Pure Base 500') == 'be quiet!'

    @pytest.mark.parametrize('name', ['', None])
    def test_empty(self, name):
        assert extract_brand(name) == ''

    def test_against_fixture(self, golden):
        for case in golden['extract_brand']:
            assert extract_brand(case['name']) == case['expected'], case['name']


class TestExtractMpn:
    def test_brackets_uppercase(self):
        mpn, src = extract_mpn('Ноутбук Lenovo ThinkPad E16 G2 [21m6s1f000_32g]')
        assert mpn == '21M6S1F000_32G'
        assert src == 'bracket'

    def test_brackets_with_slash(self):
        mpn, src = extract_mpn('Apple MacBook Pro 16 [mkgt3ru/a]')
        assert mpn == 'MKGT3RU/A'
        assert src == 'bracket'

    def test_freeform_in_name(self):
        mpn, src = extract_mpn('ASUS Vivobook 17 X1704VA-AU982 16GB')
        assert mpn == 'X1704VA-AU982'
        assert src == 'name'

    def test_hint_wins_over_brackets(self):
        mpn, src = extract_mpn(
            'ASUS Vivobook [au982]', hint='X1704VA-AU982',
        )
        assert mpn == 'X1704VA-AU982'
        assert src == 'mpn_hint'

    def test_sku_used_when_mpn_like(self):
        mpn, src = extract_mpn(
            'Без MPN в имени', sku='X1704VA-AU982',
        )
        assert mpn == 'X1704VA-AU982'
        assert src == 'sku'

    def test_sku_ignored_when_pure_digits(self):
        mpn, _ = extract_mpn('Без MPN в имени', sku='1933481')
        assert mpn == ''

    def test_url_with_internal_id_ignored(self):
        mpn, _ = extract_mpn('Ноутбук', url='https://ozon.ru/product/wb-15692-1234567/')
        assert mpn == ''

    def test_no_mpn(self):
        assert extract_mpn('Ноутбук без артикула')[0] == ''

    def test_promo_text_not_mpn(self):

        mpn, _ = extract_mpn('Получите 1500 баллов за отзыв')
        assert mpn == ''


class TestExtractSpecs:
    def test_ram_gb_basic(self):
        assert extract_specs('16ГБ DDR5 RAM Core 5')['ram_gb'] == 16

    def test_ram_alternative_gb(self):
        assert extract_specs('16 GB DDR4 ОЗУ')['ram_gb'] == 16

    def test_ram_lowercase_with_ddr(self):
        assert extract_specs('16Gb DDR4 RAM')['ram_gb'] == 16

    def test_storage_tb(self):
        assert extract_specs('1ТБ SSD NVMe')['storage_gb'] == 1024

    def test_storage_gb_512(self):
        assert extract_specs('512ГБ SSD M.2')['storage_gb'] == 512

    def test_storage_256(self):
        assert extract_specs('256GB NVMe')['storage_gb'] == 256

    def test_screen_15_6(self):
        assert extract_specs('Ноутбук 15.6" FHD')['screen_in'] == '15.6'

    def test_screen_16(self):
        assert extract_specs('Монитор 16" IPS')['screen_in'] == '16'

    def test_screen_comma(self):
        assert extract_specs('MacBook 16,2" M4 Pro')['screen_in'] == '16.2'

    def test_promo_noise_ignored(self):

        out = extract_specs('Получите 1500 баллов за отзыв на ноутбук')
        assert 'ram_gb' not in out
        assert 'storage_gb' not in out
        assert 'screen_in' not in out

    def test_gpu_family(self):
        out = extract_specs('ASUS RTX 4070 Dual 12GB GPU')
        assert out['gpu_family'] == 'rtx 4070'

    def test_apple_silicon(self):
        out = extract_specs('Apple MacBook Pro M4 Pro 2024')
        assert out['cpu_family'] == 'apple m4'
        assert out['year'] == 2024

    def test_against_fixture(self, golden):
        for case in golden['extract_specs']:
            actual = extract_specs(case['name'])
            for k, v in case['expected'].items():
                assert actual.get(k) == v, (case['name'], k, actual)


class TestSpecsContradict:
    def test_ram_conflict(self):
        assert specs_contradict({'ram_gb': 16}, {'ram_gb': 32}) is True

    def test_ram_subset_no_conflict(self):

        assert specs_contradict({'ram_gb': 16}, {'storage_gb': 512}) is False

    def test_screen_decimal_string(self):
        assert specs_contradict({'screen_in': '15.6'}, {'screen_in': '16'}) is True

    def test_empty(self):
        assert specs_contradict({}, {'ram_gb': 16}) is False
        assert specs_contradict({}, {}) is False


class TestDice:
    def test_identical_sets(self):
        assert dice({'asus', 'rog'}, {'asus', 'rog'}) == 1.0

    def test_disjoint(self):
        assert dice({'a', 'b'}, {'c', 'd'}) == 0.0

    def test_partial(self):

        assert dice({'a', 'b'}, {'b', 'c'}) == 0.5

    def test_empty(self):
        assert dice(set(), {'a'}) == 0.0


class TestNormalizeOffer:
    def test_smoke_dns(self):
        f = normalize_offer(
            name='Ноутбук Lenovo ThinkPad E16 G2 [21m6s1f000_32g] 32ГБ 1ТБ',
            source='dns',
            category_id=1,
            sku='21M6S1F000',
            url='https://www.dns-shop.ru/product/abc/',
        )
        assert f.brand == 'lenovo'
        assert f.model_code == '21M6S1F000_32G'
        assert f.specs.get('ram_gb') == 32
        assert f.specs.get('storage_gb') == 1024
        assert f.source == 'dns'
        assert f.category_id == 1

        assert 'lenovo' in f.tokens
        assert 'thinkpad' in f.tokens

    def test_jsonable_roundtrip(self):
        f = normalize_offer(
            name='ASUS Vivobook 17 X1704VA-AU982 16ГБ 512ГБ',
            source='dns',
            category_id=2,
            sku='',
            url='',
        )
        from apps.products.dedupe.features import Features

        f2 = Features.from_jsonable(f.to_jsonable())
        assert f2.brand == f.brand
        assert f2.model_code == f.model_code
        assert f2.specs == f.specs

    def test_key_hash_stable(self):
        f1 = normalize_offer(
            name='ASUS Vivobook X1704VA-AU982 16ГБ 512ГБ',
            source='dns', category_id=1, sku='', url='',
        )
        f2 = normalize_offer(
            name='ноутбук asus vivobook x1704va-au982 16гб 512гб',
            source='ozon', category_id=1, sku='', url='',
        )

        assert f1.key_hash == f2.key_hash


class TestVariantUrl:
    def test_citilink_preserves_config_query(self):
        raw = 'https://www.citilink.ru/product/foo-123/?config=16GB&utm_source=x'
        canon = normalize_offer_url(raw, source='citilink')
        assert 'config=16GB' in canon or 'config=16gb' in canon.lower()
        assert 'utm' not in canon

    def test_dns_strips_utm_only(self):
        raw = 'https://www.dns-shop.ru/product/foo/?utm=1'
        canon = normalize_offer_url(raw, source='dns')
        assert 'utm' not in canon

    def test_extract_variant_specs(self):
        label, specs = extract_variant_from_url(
            'https://www.citilink.ru/product/x/?config=16GB+512GB'
        )
        assert label
        assert specs.get('variant_key')
