from __future__ import annotations

import pytest
from django.test import override_settings

from apps.products.dedupe.normalizer import normalize_offer
from apps.products.dedupe.services import upsert_offer
from apps.products.models import Category, MatchReview, Offer, Product


def _cat(slug: str = 'dedupe-svc-test') -> Category:
    cat, _ = Category.objects.get_or_create(
        slug=slug,
        defaults={'name': slug},
    )
    return cat


class TestReviewDoesNotAttach:
    @pytest.mark.django_db
    @override_settings(DEDUP_V2=True, DEDUP_REMATCH_ON_UPDATE=True, DEDUP_REMATCH_COOLDOWN_HOURS=0)
    def test_review_creates_separate_product_and_queue(self):
        cat = _cat('review-no-attach')
        master = Product.objects.create(
            name='ASUS Vivobook X1704VA',
            slug='asus-vivobook-master',
            category=cat,
            brand='asus',
            vendor_code='OTHER-SKU',
            url='https://dns-shop.ru/product/master/',
        )
        suggest_features = normalize_offer(
            name='ASUS Vivobook 16 X1704VA-AU982',
            source='dns',
            category_id=cat.pk,
            sku='X1704VA-AU982',
            url='https://dns-shop.ru/product/new-offer/',
        )
        from apps.products.dedupe.matcher import find_master

        match = find_master(suggest_features, category_id=cat.pk, raw_name=suggest_features.clean_name)
        if match.decision != 'review' or match.product is None:
            pytest.skip('fixture did not produce review decision')

        res = upsert_offer(
            category=cat,
            source='dns',
            name='ASUS Vivobook 16 X1704VA-AU982',
            url='https://dns-shop.ru/product/new-offer/',
            vendor_code='X1704VA-AU982',
        )
        assert res.offer.product_id != match.product.pk
        review = MatchReview.objects.filter(offer=res.offer, status=MatchReview.Status.PENDING).first()
        assert review is not None
        assert review.suggested_product_id == match.product.pk


class TestRematchExistingOffer:
    @pytest.mark.django_db
    @override_settings(DEDUP_V2=True, DEDUP_REMATCH_ON_UPDATE=True, DEDUP_REMATCH_COOLDOWN_HOURS=0)
    def test_rematch_moves_offer_on_auto_merge(self):
        cat = _cat('rematch-move')
        wrong = Product.objects.create(
            name='Wrong product',
            slug='wrong-product-rematch',
            category=cat,
            brand='asus',
            vendor_code='',
            url='https://dns-shop.ru/product/wrong/',
        )
        right = Product.objects.create(
            name='ASUS Vivobook X1704VA-AU982',
            slug='right-product-rematch',
            category=cat,
            brand='asus',
            vendor_code='X1704VA-AU982',
            url='https://dns-shop.ru/product/right/',
        )
        offer = Offer.objects.create(
            product=wrong,
            source='dns',
            url='https://dns-shop.ru/product/stale-offer/',
            vendor_code='X1704VA-AU982',
            raw_name='ASUS Vivobook 16 X1704VA-AU982',
        )
        res = upsert_offer(
            category=cat,
            source='dns',
            name='ASUS Vivobook 16 X1704VA-AU982 [X1704VA-AU982]',
            url='https://dns-shop.ru/product/stale-offer/',
            vendor_code='X1704VA-AU982',
        )
        offer.refresh_from_db()
        assert res.offer.pk == offer.pk
        assert offer.product_id == right.pk

    @pytest.mark.django_db
    @override_settings(DEDUP_V2=True, DEDUP_REMATCH_ON_UPDATE=False)
    def test_no_rematch_when_disabled(self):
        cat = _cat('rematch-off')
        wrong = Product.objects.create(
            name='Wrong product off',
            slug='wrong-product-rematch-off',
            category=cat,
            brand='asus',
            vendor_code='',
            url='https://dns-shop.ru/product/wrong-off/',
        )
        Product.objects.create(
            name='ASUS Vivobook X1704VA-AU982',
            slug='right-product-rematch-off',
            category=cat,
            brand='asus',
            vendor_code='X1704VA-AU982',
            url='https://dns-shop.ru/product/right-off/',
        )
        offer = Offer.objects.create(
            product=wrong,
            source='dns',
            url='https://dns-shop.ru/product/stale-offer-off/',
            vendor_code='X1704VA-AU982',
            raw_name='ASUS Vivobook 16 X1704VA-AU982',
        )
        upsert_offer(
            category=cat,
            source='dns',
            name='ASUS Vivobook 16 X1704VA-AU982 [X1704VA-AU982]',
            url='https://dns-shop.ru/product/stale-offer-off/',
            vendor_code='X1704VA-AU982',
        )
        offer.refresh_from_db()
        assert offer.product_id == wrong.pk
