import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.products.models import Category, Offer, Product
from apps.prices.models import PriceHistory

User = get_user_model()


@pytest.mark.django_db
class TestProductAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def product(self):
        cat = Category.objects.create(name='ОЗУ', slug='ozu')
        p = Product.objects.create(
            name='Test RAM', slug='test-ram', category=cat,
            url='https://dns-shop.ru/product/1/',
        )
        # Каталог показывает только товары с офффером, у которого есть цена.
        Offer.objects.create(
            product=p, source='dns', url='https://dns-shop.ru/product/1/',
            current_price=Decimal('4999.00'), is_available=True,
        )
        PriceHistory.objects.create(
            product=p, price=Decimal('4999.00'), timestamp=timezone.now(),
        )
        return p

    def test_product_list(self, client, product):
        response = client.get('/api/products/')
        assert response.status_code == 200
        assert len(response.data['results']) == 1

    def test_product_detail(self, client, product):
        response = client.get(f'/api/products/{product.pk}/')
        assert response.status_code == 200
        assert response.data['name'] == 'Test RAM'

    def test_price_history_endpoint(self, client, product):
        response = client.get(f'/api/products/{product.pk}/price-history/')
        assert response.status_code == 200

    def test_offer_uses_pricehistory_when_current_price_missing(self, client, product):
        offer = Offer.objects.create(
            product=product,
            source='wb',
            url='https://wildberries.ru/catalog/1/detail.aspx',
            current_price=None,
            is_available=True,
        )
        PriceHistory.objects.create(
            product=product,
            offer=offer,
            source='wb',
            price=Decimal('3210.00'),
            old_price=Decimal('3999.00'),
            timestamp=timezone.now(),
            is_actual=True,
        )

        response = client.get(f'/api/products/{product.pk}/')
        assert response.status_code == 200
        wb_offer = next(o for o in response.data['offers'] if o['id'] == offer.id)
        assert wb_offer['current_price'] == '3210.00'
        assert wb_offer['old_price'] == '3999.00'

    def test_offer_falls_back_to_product_source_history(self, client, product):
        offer = Offer.objects.create(
            product=product,
            source='mvideo',
            url='https://www.mvideo.ru/products/1',
            current_price=None,
            is_available=True,
        )
        PriceHistory.objects.create(
            product=product,
            source='mvideo',
            price=Decimal('7777.00'),
            timestamp=timezone.now(),
            is_actual=True,
        )

        response = client.get(f'/api/products/{product.pk}/')
        assert response.status_code == 200
        mvideo_offer = next(o for o in response.data['offers'] if o['id'] == offer.id)
        assert mvideo_offer['current_price'] == '7777.00'

    def test_best_offer_image_prefers_citilink_over_wb_without_dns(self, client, product):
        Offer.objects.create(
            product=product,
            source='wb',
            url='https://wildberries.ru/catalog/2/detail.aspx',
            current_price=Decimal('4500.00'),
            image_url='https://img.wb.local/wb.jpg',
            is_available=True,
        )
        Offer.objects.create(
            product=product,
            source='citilink',
            url='https://www.citilink.ru/product/2/',
            current_price=Decimal('5200.00'),
            image_url='https://img.cit.local/cit.jpg',
            is_available=True,
        )
        response = client.get(f'/api/products/{product.pk}/')
        assert response.status_code == 200
        assert response.data['best_offer']['image_url'] == 'https://img.cit.local/cit.jpg'

    def test_best_offer_image_prefers_mvideo_when_dns_and_citilink_absent(self, client, product):
        Offer.objects.create(
            product=product,
            source='wb',
            url='https://wildberries.ru/catalog/3/detail.aspx',
            current_price=Decimal('4300.00'),
            image_url='https://img.wb.local/wb2.jpg',
            is_available=True,
        )
        Offer.objects.create(
            product=product,
            source='mvideo',
            url='https://www.mvideo.ru/products/3',
            current_price=Decimal('5300.00'),
            image_url='https://img.mv.local/mv.jpg',
            is_available=True,
        )
        response = client.get(f'/api/products/{product.pk}/')
        assert response.status_code == 200
        assert response.data['best_offer']['image_url'] == 'https://img.mv.local/mv.jpg'


@pytest.mark.django_db
class TestSubscriptionAPI:
    @pytest.fixture
    def auth_client(self):
        user = User.objects.create_user(
            username='apiuser', email='api@test.com', password='pass123',
        )
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def product(self):
        cat = Category.objects.create(name='ОЗУ', slug='ozu')
        return Product.objects.create(
            name='Test RAM', slug='test-ram', category=cat,
            url='https://dns-shop.ru/product/1/',
        )

    def test_create_subscription(self, auth_client, product):
        response = auth_client.post('/api/subscriptions/', {
            'product_id': product.pk,
            'target_price': '3000.00',
        })
        assert response.status_code == 201

    def test_list_subscriptions(self, auth_client):
        response = auth_client.get('/api/subscriptions/')
        assert response.status_code == 200

    def test_unauthorized_access(self, product):
        client = APIClient()
        response = client.post('/api/subscriptions/', {
            'product': product.pk,
            'target_price': '3000.00',
        })
        assert response.status_code in (401, 403)
