from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.alerts.models import Notification, Subscription
from apps.analytics.models import Anomaly
from apps.prices.models import PriceHistory
from apps.products.models import Offer, Product

from .serializers import (
    AnomalySerializer,
    NotificationSerializer,
    OfferSerializer,
    PriceHistorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    SubscriptionSerializer,
)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Product.objects
        .filter(is_active=True)
        .select_related('category')
        .prefetch_related('offers', 'category__listings')
    )
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['category__slug', 'is_active']
    search_fields = ['name', 'vendor_code']
    ordering_fields = ['name', 'last_parsed_at', 'created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer

    @action(detail=True, methods=['get'], url_path='price-history')
    def price_history(self, request: Request, pk: int | None = None) -> Response:
        product = self.get_object()
        prices = PriceHistory.objects.filter(product=product).order_by('-timestamp')[:300]
        return Response(PriceHistorySerializer(prices, many=True).data)

    @action(detail=True, methods=['get'], url_path='offers')
    def offers(self, request: Request, pk: int | None = None) -> Response:
        product = self.get_object()
        offers = product.offers.all().order_by('source')
        return Response(OfferSerializer(offers, many=True).data)


class OfferViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Offer.objects.select_related('product', 'product__category').all()
    serializer_class = OfferSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['source', 'product', 'product__category__slug', 'is_available']
    search_fields = ['product__name', 'vendor_code']
    ordering_fields = ['last_seen_at', 'source']


class SubscriptionViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Subscription.objects
            .filter(user=self.request.user)
            .select_related('product')
        )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class AnomalyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Anomaly.objects.select_related('product').all()
    serializer_class = AnomalySerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['severity', 'anomaly_type', 'resolved', 'product']
    ordering_fields = ['detected_at', 'severity']
