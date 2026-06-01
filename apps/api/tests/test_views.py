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
