from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from django_filters import FilterSet, CharFilter
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from apps.alerts.models import Notification, Subscription, Wishlist, WishlistItem
from apps.analytics.models import Anomaly
from apps.core.models import User
from apps.prices.models import PriceHistory
from apps.products.models import Category, Offer, Product, ProductFamily

from .serializers import (
    AnomalySerializer,
    CategoryMinimalSerializer,
    CategorySerializer,
    NotificationSerializer,
    OfferSerializer,
    PriceHistorySerializer,
    ProductDetailSerializer,
    ProductFamilyListSerializer,
    ProductFamilySerializer,
    ProductListSerializer,
    SubscriptionSerializer,
    WishlistItemSerializer,
    WishlistSerializer,
    UserSerializer,
    UserRegisterSerializer,
)


class ProductFilterSet(FilterSet):
    source = CharFilter(field_name='offers__source', distinct=True)
    category_slug = CharFilter(method='filter_category_slug')

    def filter_category_slug(self, queryset, name, value):
        try:
            cat = Category.objects.get(slug=value, is_active=True)
            ids = cat.descendants_ids()
            return queryset.filter(category_id__in=ids).distinct()
        except Category.DoesNotExist:
            return queryset.none()

    class Meta:
        model = Product
        fields = ['category', 'is_active']


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Product.objects
        .filter(is_active=True)
        .select_related('category')
        .prefetch_related('offers', 'category__listings')
    )
    permission_classes = [permissions.AllowAny]
    filterset_class = ProductFilterSet
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


class ProductFamilyFilterSet(FilterSet):
    category_slug = CharFilter(method='filter_category_slug')

    def filter_category_slug(self, queryset, name, value):
        try:
            cat = Category.objects.get(slug=value, is_active=True)
            ids = cat.descendants_ids()
            return queryset.filter(category_id__in=ids).distinct()
        except Category.DoesNotExist:
            return queryset.none()

    class Meta:
        model = ProductFamily
        fields = ['category', 'brand', 'is_active']


class ProductFamilyViewSet(viewsets.ReadOnlyModelViewSet):
    """Семьи товаров: одна модель — несколько вариантов конфигов (RAM/SSD/...).

    - `/api/families/` — список семей с диапазоном цен и счётчиком вариантов.
    - `/api/families/<id>/` — детали с полным списком variants и лучшими офферами.
    """

    queryset = (
        ProductFamily.objects
        .filter(is_active=True)
        .select_related('category')
        .prefetch_related('variants', 'variants__offers')
    )
    permission_classes = [permissions.AllowAny]
    filterset_class = ProductFamilyFilterSet
    search_fields = ['name', 'brand', 'model_code']
    ordering_fields = ['name', 'brand', 'created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductFamilySerializer
        return ProductFamilyListSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True).order_by('name')
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['parent']

    def get_serializer_class(self):
        if self.action == 'list':
            return CategoryMinimalSerializer
        return CategorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('root'):
            qs = qs.filter(parent__isnull=True)
        return qs


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


class WishlistViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request: Request) -> Response:
        if request.method == 'PATCH':
            wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
            serializer = WishlistSerializer(wishlist, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        serializer = WishlistSerializer(wishlist)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add_item(self, request: Request) -> Response:
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        if not product_id:
            return Response({'error': 'product_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product,
            defaults={'quantity': quantity, 'note': request.data.get('note', '')},
        )
        if not created:
            item.quantity = quantity
            if 'note' in request.data:
                item.note = request.data['note']
            item.save()

        serializer = WishlistItemSerializer(item)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='remove-item/(?P<item_id>[^/.]+)')
    def remove_item(self, request: Request, item_id: int | None = None) -> Response:
        try:
            item = WishlistItem.objects.get(id=item_id, wishlist__user=request.user)
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except WishlistItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request: Request) -> Response:
    serializer = UserRegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        Wishlist.objects.create(user=user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request: Request) -> Response:
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {'error': 'Username and password required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request: Request) -> Response:
    logout(request)
    return Response({'message': 'Logged out'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def me_view(request: Request) -> Response:
    serializer = UserSerializer(request.user)
    return Response(serializer.data)
