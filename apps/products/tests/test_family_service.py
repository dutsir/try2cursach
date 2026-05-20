from __future__ import annotations

import pytest

from apps.products.dedupe.family_service import attach_product_to_family
from apps.products.models import Category, Product, ProductFamily


def _cat(slug: str = 'ssd-nakopiteli') -> Category:
    cat, _ = Category.objects.get_or_create(slug=slug, defaults={'name': slug})
    return cat


def _product(name: str, *, slug: str, category: Category, **kwargs) -> Product:
    return Product.objects.create(
        name=name, slug=slug, category=category,
        url='https://example.com/' + slug, **kwargs,
    )


class TestAttachProductToFamily:
    @pytest.mark.django_db
    def test_attaches_and_creates_family(self) -> None:
        cat = _cat('ssd-nakopiteli')
        p = _product(
            '1024 ГБ SSD M.2 2280 Samsung 980 PRO MZ-V8P1T0BW',
            slug='attach-980pro-1tb', category=cat,
            brand='samsung', vendor_code='MZ-V8P1T0BW',
            specs_fingerprint={'storage_gb': 1024},
        )
        family = attach_product_to_family(p, category_slug='ssd-nakopiteli')
        assert family is not None
        p.refresh_from_db()
        assert p.family_id == family.id
        assert p.variant_specs == {'storage_gb': 1024}
        assert p.variant_key_hash and len(p.variant_key_hash) == 40

    @pytest.mark.django_db
    def test_two_variants_share_one_family(self) -> None:
        cat = _cat('ssd-nakopiteli')
        a = _product(
            '500 ГБ SSD M.2 2280 Samsung 980 PRO MZ-V8P500BW',
            slug='attach-980pro-500gb', category=cat,
            brand='samsung', vendor_code='MZ-V8P500BW',
            specs_fingerprint={'storage_gb': 500},
        )
        b = _product(
            '1024 ГБ SSD M.2 2280 Samsung 980 PRO MZ-V8P1T0BW',
            slug='attach-980pro-1tb-2', category=cat,
            brand='samsung', vendor_code='MZ-V8P1T0BW',
            specs_fingerprint={'storage_gb': 1024},
        )
        fa = attach_product_to_family(a, category_slug='ssd-nakopiteli')
        fb = attach_product_to_family(b, category_slug='ssd-nakopiteli')
        assert fa and fb
        assert fa.id == fb.id, 'разные variants одной семьи должны делить ProductFamily'
        # variant_key_hash должен отличаться у разных вариантов.
        a.refresh_from_db(); b.refresh_from_db()
        assert a.variant_key_hash != b.variant_key_hash

    @pytest.mark.django_db
    def test_idempotent_no_double_save(self) -> None:
        cat = _cat('ssd-nakopiteli')
        p = _product(
            '1024 ГБ SSD Samsung 980 PRO MZ-V8P1T0BW',
            slug='attach-idem', category=cat,
            brand='samsung', vendor_code='MZ-V8P1T0BW',
            specs_fingerprint={'storage_gb': 1024},
        )
        f1 = attach_product_to_family(p, category_slug='ssd-nakopiteli')
        before_count = ProductFamily.objects.count()
        f2 = attach_product_to_family(p, category_slug='ssd-nakopiteli')
        after_count = ProductFamily.objects.count()
        assert f1.id == f2.id
        assert before_count == after_count, 'повторный attach не должен создавать новую семью'

    @pytest.mark.django_db
    def test_cpu_category_returns_none(self) -> None:
        cat = _cat('processory')
        p = _product(
            'Процессор Intel Core i5-13400F BOX',
            slug='attach-cpu', category=cat,
            brand='intel', vendor_code='BX8071513400F',
            specs_fingerprint={'cpu_family': 'core i5'},
        )
        family = attach_product_to_family(p, category_slug='processory')
        assert family is None
        p.refresh_from_db()
        assert p.family_id is None  # семья не создаётся для категорий без variants

    @pytest.mark.django_db
    def test_garbage_card_returns_none(self) -> None:
        cat = _cat('noutbuki')
        p = _product(
            '600 баллов за отзыв',
            slug='attach-garbage', category=cat,
        )
        family = attach_product_to_family(p, category_slug='noutbuki')
        assert family is None  # префикс «Ноутбук» отсутствует → экстрактор отказывается
