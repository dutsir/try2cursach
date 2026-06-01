import logging

from django.contrib.auth import authenticate, login, logout
from django.db.models import (
    Count, DecimalField, Exists, ExpressionWrapper, F,
    Max, Min, OuterRef, Q, Value,
)
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django_filters import (
    BooleanFilter, CharFilter, FilterSet, NumberFilter,
)
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.models import Notification, Subscription, Wishlist, WishlistItem
from apps.core.models import User
from apps.prices.models import PriceHistory
from apps.prices.stats import compute_product_price_stats
from apps.products.models import Category, Offer, Product

logger = logging.getLogger(__name__)

from .serializers import (
    CategoryMinimalSerializer,
    CategorySerializer,
    NotificationSerializer,
    OfferSerializer,
    PriceHistorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    SubscriptionSerializer,
    WishlistItemSerializer,
    WishlistSerializer,
    UserSerializer,
    UserRegisterSerializer,
)


class ProductFilterSet(FilterSet):
    source = CharFilter(method='filter_source')
    category_slug = CharFilter(method='filter_category_slug')
    brand = CharFilter(method='filter_brand')
    min_price = NumberFilter(method='filter_min_price')
    max_price = NumberFilter(method='filter_max_price')
    in_stock = BooleanFilter(method='filter_in_stock')

    def filter_category_slug(self, queryset, name, value):
        try:
            cat = Category.objects.get(slug=value, is_active=True)
            ids = cat.descendants_ids()
            return queryset.filter(category_id__in=ids).distinct()
        except Category.DoesNotExist:
            return queryset.none()

    def filter_source(self, queryset, name, value):
        """Поддерживает comma-separated: ?source=dns,wb"""
        sources = [s.strip() for s in (value or '').split(',') if s.strip()]
        if not sources:
            return queryset
        return queryset.filter(offers__source__in=sources).distinct()

    def filter_brand(self, queryset, name, value):
        """Поддерживает comma-separated case-insensitive: ?brand=ASUS,MSI,asus"""
        brands = [b.strip() for b in (value or '').split(',') if b.strip()]
        if not brands:
            return queryset
        q = Q()
        for b in brands:
            q |= Q(brand__iexact=b)
        return queryset.filter(q)

    def filter_min_price(self, queryset, name, value):
        return queryset.filter(offers__current_price__gte=value).distinct()

    def filter_max_price(self, queryset, name, value):
        return queryset.filter(offers__current_price__lte=value).distinct()

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(offers__is_available=True).distinct()
        return queryset

    class Meta:
        model = Product
        fields = ['category', 'is_active']


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Product.objects
        .filter(is_active=True)
        # Только товары, у которых хотя бы один оффер с известной ценой.
        # Офферы без цены (current_price=null/0) — парсинг ещё не добрался или
        # листинг снят — скрываем из каталога целиком.
        .filter(Exists(Offer.objects.filter(product=OuterRef('pk'), current_price__gt=0)))
        .select_related('category')
        .prefetch_related('offers', 'category__listings')
    )
    permission_classes = [permissions.AllowAny]
    filterset_class = ProductFilterSet
    search_fields = ['name', 'vendor_code']
    ordering_fields = ['name', 'last_parsed_at', 'created_at', 'min_price']

    def get_queryset(self):
        qs = super().get_queryset()
        # Annotate min_price для сортировки по цене (минимум денормализованной Offer.current_price)
        if 'min_price' in (self.request.query_params.get('ordering') or ''):
            qs = qs.annotate(min_price=Min('offers__current_price'))
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer

    @action(detail=True, methods=['get'], url_path='price-history')
    def price_history(self, request: Request, pk: int | None = None) -> Response:
        product = self.get_object()
        prices = PriceHistory.objects.filter(product=product).order_by('-timestamp')[:300]
        return Response(PriceHistorySerializer(prices, many=True).data)

    @action(detail=True, methods=['get'], url_path='price-stats')
    def price_stats(self, request: Request, pk: int | None = None) -> Response:
        """Возвращает агрегаты PriceStats: за всё время, 30д, 7д.

        current_price берётся как минимальная цена среди доступных офферов
        (зеркало логики в шаблоне catalog/product.html).
        """
        product = self.get_object()

        # current_price: best price среди денормализованных Offer.current_price.
        offers = list(product.offers.all())
        offer_prices: list[tuple[int, bool]] = []  # (price, is_available)
        for offer in offers:
            if offer.current_price and offer.current_price > 0:
                offer_prices.append((int(offer.current_price), bool(offer.is_available)))

        available = [p for p, av in offer_prices if av]
        if available:
            current_price: int | None = min(available)
        else:
            any_prices = [p for p, _ in offer_prices]
            current_price = min(any_prices) if any_prices else None

        stats = compute_product_price_stats(product, current_price=current_price)

        def _iso(d):
            return d.isoformat() if d else None

        payload = {
            'current': stats.current,
            'history_points': stats.history_points,
            'all_time': {
                'min': stats.min_price,
                'min_date': _iso(stats.min_date),
                'max': stats.max_price,
                'max_date': _iso(stats.max_date),
            },
            'window_30d': {
                'min': stats.min_price_30d,
                'min_date': _iso(stats.min_date_30d),
                'max': stats.max_price_30d,
                'max_date': _iso(stats.max_date_30d),
                'avg': stats.avg_30d,
                'points': stats.points_30d,
            },
            'window_7d': {
                'min': stats.min_price_7d,
                'min_date': _iso(stats.min_date_7d),
                'max': stats.max_price_7d,
                'max_date': _iso(stats.max_date_7d),
                'avg': stats.avg_7d,
                'points': stats.points_7d,
            },
            'delta_7d_pct': stats.delta_7d_pct,
            'delta_30d_pct': stats.delta_30d_pct,
            'is_min_30d': stats.is_min_30d,
            'is_min_all_time': stats.is_min_all_time,
            'drop_alert': stats.drop_alert,
            'drop_alert_pct': stats.drop_alert_pct,
        }
        return Response(payload)


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

    @action(detail=False, methods=['get'])
    def tree(self, request: Request) -> Response:
        """Иерархия категорий (родитель → дети) со счётчиками товаров.

        URL: /api/categories/tree/

        product_count считает только активные товары, у которых есть хотя бы
        один оффер (как в каталоге). Пустые категории и пустые ветки опускаются.
        """
        # Кол-во товаров (с офферами) по category_id — одним запросом.
        counts = dict(
            Product.objects
            .filter(is_active=True)
            .filter(Exists(Offer.objects.filter(product=OuterRef('pk'))))
            .values('category_id')
            .annotate(c=Count('id'))
            .values_list('category_id', 'c')
        )

        cats = list(Category.objects.filter(is_active=True).order_by('name'))
        children_by_parent: dict[int | None, list[Category]] = {}
        for c in cats:
            children_by_parent.setdefault(c.parent_id, []).append(c)

        def build(cat: Category) -> dict | None:
            kids = [
                node for node in (
                    build(child) for child in children_by_parent.get(cat.id, [])
                ) if node is not None
            ]
            own = counts.get(cat.id, 0)
            total = own + sum(k['product_count'] for k in kids)
            if total == 0:
                return None
            return {
                'id': cat.id,
                'slug': cat.slug,
                'name': cat.name,
                'product_count': total,
                'children': kids,
            }

        roots = [
            node for node in (
                build(root) for root in children_by_parent.get(None, [])
            ) if node is not None
        ]
        return Response(roots)


class CategoryFacetsView(APIView):
    """Фасеты для sidebar фильтров каталога: brands, price_range, sources, total.

    URL: /api/categories/<slug>/facets/

    Возвращает агрегаты по категории и её подкатегориям:
    - brands: топ-30 брендов (case-folded) с count
    - price_range: min/max из актуальных PriceHistory
    - sources: распределение по магазинам
    - total_products: всего активных Product
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, slug: str) -> Response:
        try:
            cat = Category.objects.get(slug=slug, is_active=True)
        except Category.DoesNotExist:
            return Response({'error': 'category not found'}, status=404)

        ids = cat.descendants_ids()
        products = Product.objects.filter(category_id__in=ids, is_active=True)

        # Brands — top 30 с count
        brands_qs = (
            products.exclude(brand='')
            .values('brand')
            .annotate(count=Count('id'))
            .order_by('-count')[:30]
        )
        brands = [{'name': b['brand'], 'count': b['count']} for b in brands_qs]

        # Price range — из денормализованной Offer.current_price
        price_agg = (
            Offer.objects
            .filter(product__in=products, current_price__gt=0)
            .aggregate(min_price=Min('current_price'), max_price=Max('current_price'))
        )
        price_range = {
            'min': int(price_agg['min_price']) if price_agg.get('min_price') else 0,
            'max': int(price_agg['max_price']) if price_agg.get('max_price') else 0,
        }

        # Sources — count distinct продуктов на каждый source
        sources_qs = (
            Offer.objects
            .filter(product__in=products)
            .values('source')
            .annotate(count=Count('product', distinct=True))
            .order_by('-count')
        )
        sources = [{'code': s['source'], 'count': s['count']} for s in sources_qs]

        return Response({
            'category': {'id': cat.id, 'slug': cat.slug, 'name': cat.name},
            'brands': brands,
            'price_range': price_range,
            'sources': sources,
            'total_products': products.count(),
        })


class DashboardView(APIView):
    """Агрегаты для главной страницы.

    URL: /api/dashboard/

    Возвращает:
      - totals: общие счётчики (products, categories, offers, records 24h)
      - top_deals: 10 товаров с наибольшим % скидки (old_price/price)
      - popular_categories: 8 категорий по числу активных продуктов
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        from datetime import timedelta
        from django.utils import timezone

        # === Totals ===
        since_24h = timezone.now() - timedelta(hours=24)
        totals = {
            # Только товары с хотя бы одним оффером с известной ценой — те же, что видно в каталоге.
            'products': Product.objects.filter(
                is_active=True,
                offers__current_price__gt=0,
            ).distinct().count(),
            'categories': Category.objects.filter(is_active=True).count(),
            'offers': Offer.objects.count(),
            'price_records_24h': PriceHistory.objects.filter(timestamp__gte=since_24h).count(),
        }

        # === Top deals: товары с актуальной скидкой (old_price > price) ===
        # Берём офферы с денормализованной скидкой (current_old_price > current_price)
        deals_qs = (
            Offer.objects
            .filter(current_old_price__gt=F('current_price'), current_price__gt=0)
            .select_related('product', 'product__category')
            .annotate(
                discount_pct=ExpressionWrapper(
                    (F('current_old_price') - F('current_price')) * 100.0 / F('current_old_price'),
                    output_field=DecimalField(max_digits=5, decimal_places=2),
                )
            )
            .order_by('-discount_pct')[:30]
        )
        # Дедупликация по product чтобы один товар не повторялся
        seen_products = set()
        top_deals = []
        for o in deals_qs:
            if o.product_id in seen_products:
                continue
            seen_products.add(o.product_id)
            top_deals.append({
                'id': o.product_id,
                'name': o.product.name,
                'slug': o.product.slug,
                'brand': o.product.brand,
                'category_name': o.product.category.name if o.product.category else '',
                'image_url': o.image_url or o.product.image_url or '',
                'price': str(o.current_price),
                'old_price': str(o.current_old_price),
                'discount_pct': int(o.discount_pct or 0),
                'source': o.source,
                'source_display': o.get_source_display(),
                'url': o.url,
            })
            if len(top_deals) >= 10:
                break

        # === Popular categories: по числу активных продуктов ===
        pop_cats_qs = (
            Category.objects.filter(is_active=True)
            .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
            .filter(product_count__gt=0)
            .order_by('-product_count')[:8]
        )
        popular_categories = [
            {
                'id': c.id,
                'slug': c.slug,
                'name': c.name,
                'count': c.product_count,
            }
            for c in pop_cats_qs
        ]

        return Response({
            'totals': totals,
            'top_deals': top_deals,
            'popular_categories': popular_categories,
        })


def _build_compare_data(ids: list[int]) -> list[dict]:
    """Собирает данные товаров для сравнения. Используется CompareView и AICompareSummaryView."""
    from datetime import timedelta
    from django.utils import timezone

    products = (
        Product.objects
        .filter(id__in=ids, is_active=True)
        .filter(Exists(Offer.objects.filter(product=OuterRef('pk'))))
        .select_related('category')
        .prefetch_related('offers')
    )

    # Сохраняем порядок как в URL
    by_id = {p.id: p for p in products}
    ordered = [by_id[i] for i in ids if i in by_id]

    result = []
    all_ratings = []

    for p in ordered:
        offers = list(p.offers.all())
        offers_by_source = {}
        best_offer = None
        best_price = None

        for o in offers:
            if o.current_price:
                offers_by_source[o.source] = {
                    'price': str(o.current_price),
                    'old_price': str(o.current_old_price) if o.current_old_price else None,
                    'source_display': o.get_source_display(),
                    'url': o.url,
                    'image_url': o.image_url or p.image_url or '',
                    'is_available': o.is_available,
                    'rating': o.extra_metadata.get('supplier_rating') if o.extra_metadata else None,
                    'reviews_count': o.extra_metadata.get('reviews_count') if o.extra_metadata else None,
                }

                if best_price is None or o.current_price < best_price:
                    best_price = o.current_price
                    best_offer = o

        price_trend = None
        if best_offer:
            o = best_offer
            thirty_days_ago = timezone.now() - timedelta(days=30)
            old_price_record = (
                PriceHistory.objects
                .filter(offer=o, timestamp__lte=thirty_days_ago)
                .order_by('-timestamp')
                .first()
            )
            if old_price_record and old_price_record.price and o.current_price:
                delta = float(o.current_price - old_price_record.price)
                delta_pct = (delta / float(old_price_record.price) * 100) if old_price_record.price else 0
                price_trend = {
                    'price_30d_ago': str(old_price_record.price),
                    'delta': str(delta),
                    'delta_pct': round(delta_pct, 1),
                }

        specs_dict = {}
        if p.variant_specs:
            specs_dict.update(p.variant_specs)
        if best_offer:
            o = best_offer
            if o.normalized_features:
                specs_dict.update(o.normalized_features)
            if o.extra_metadata:
                for k, v in o.extra_metadata.items():
                    if k not in ['rating', 'supplier_rating', 'reviews_count', 'sale_percent', 'cashback_percent', 'supplier']:
                        specs_dict[k] = v

        stats = {}
        if best_offer:
            o = best_offer
            if o.extra_metadata:
                meta = o.extra_metadata
                stats = {
                    'rating': meta.get('rating'),
                    'reviews_count': meta.get('reviews_count'),
                    'sale_percent': meta.get('sale_percent'),
                    'cashback_percent': meta.get('cashback_percent'),
                    'supplier': meta.get('supplier'),
                    'supplier_rating': meta.get('supplier_rating'),
                }
                if stats.get('rating'):
                    all_ratings.append(float(stats['rating']))

        best_info = None
        if best_offer:
            o = best_offer
            best_info = {
                'price': str(o.current_price),
                'old_price': str(o.current_old_price) if o.current_old_price else None,
                'source': o.source,
                'source_display': o.get_source_display(),
                'url': o.url,
                'image_url': o.image_url or p.image_url or '',
            }

        result.append({
            'id': p.id,
            'name': p.name,
            'slug': p.slug,
            'brand': p.brand,
            'category': {'id': p.category.id, 'slug': p.category.slug, 'name': p.category.name} if p.category else None,
            'image_url': p.image_url or '',
            'best_offer': best_info,
            'offers_by_source': offers_by_source,
            'price_trend': price_trend,
            'stats': stats,
            'specs': specs_dict,
            'offers_count': len(offers),
        })

    max_rating = max(all_ratings) if all_ratings else 5.0
    prices_only = [float(item['best_offer']['price']) for item in result if item['best_offer']]
    min_price = min(prices_only) if prices_only else 0
    max_price = max(prices_only) if prices_only else 0

    for item in result:
        if item['best_offer']:
            price = float(item['best_offer']['price'])
            rating = item['stats'].get('rating')
            cashback = item['stats'].get('cashback_percent', 0) or 0
            discount = item['stats'].get('sale_percent', 0) or 0

            price_norm = 1 - ((price - min_price) / (max_price - min_price)) if max_price > min_price else 0.5
            rating_norm = (float(rating) / max_rating) if rating else 0
            benefit_norm = (float(cashback) + float(discount)) / 100.0

            value_score = (rating_norm * 0.4) + (price_norm * 0.4) + (benefit_norm * 0.2)
            item['value_score'] = round(value_score * 100, 1)
        else:
            item['value_score'] = 0

    return result


class CompareView(APIView):
    """Сравнение товаров для страницы /compare."""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        ids_param = request.query_params.get('ids', '')
        try:
            ids = [int(x.strip()) for x in ids_param.split(',') if x.strip()]
        except ValueError:
            return Response({'error': 'ids must be comma-separated integers'}, status=400)
        if not ids:
            return Response({'error': 'ids required'}, status=400)
        if len(ids) > 4:
            return Response({'error': 'maximum 4 products'}, status=400)

        result = _build_compare_data(ids)
        return Response(result)


class AICompareSummaryView(APIView):
    """AI-генерация краткого вердикта (3-5 предложений) для сравниваемых товаров.

    Использует Google Gemini, кэширует результат в Redis на 24ч.
    Rate limit: 10 запросов в минуту на IP.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        from apps.analytics.ai_compare import generate_compare_summary, AIServiceError
        from django.core.cache import cache

        ids_param = request.query_params.get('ids', '')
        try:
            ids = [int(x.strip()) for x in ids_param.split(',') if x.strip()]
        except ValueError:
            return Response({'error': 'ids must be comma-separated integers'}, status=400)
        if not ids or len(ids) < 2:
            return Response({'error': 'нужно минимум 2 товара'}, status=400)
        if len(ids) > 4:
            return Response({'error': 'максимум 4 товара'}, status=400)

        # Rate limiting: 10 запросов в минуту на IP
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'unknown'))
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        rate_key = f'ai_compare_rate:{client_ip}'
        count = cache.get(rate_key, 0)
        if count >= 10:
            return Response(
                {'error': 'Превышен лимит запросов (10/мин). Подожди немного.'},
                status=429,
            )
        cache.set(rate_key, count + 1, timeout=60)

        items = _build_compare_data(ids)
        if len(items) < 2:
            return Response({'error': 'товары не найдены'}, status=404)

        try:
            data = generate_compare_summary(items)
            return Response(data)
        except AIServiceError as exc:
            return Response({'error': str(exc)}, status=503)
        except Exception as exc:
            logger.exception('AI compare unexpected error')
            return Response({'error': 'Неожиданная ошибка генерации'}, status=500)


class SubscriptionViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
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


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def unread_count(self, request: Request) -> Response:
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread': count})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request: Request) -> Response:
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'marked': updated})


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


@ensure_csrf_cookie
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request: Request) -> Response:
    serializer = UserRegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        Wishlist.objects.create(user=user)
        login(request, user)
        # Отправляем письмо верификации; тихо игнорируем ошибку SMTP —
        # регистрация должна пройти даже если почта не настроена.
        try:
            from apps.alerts.email_notify import send_verification_email
            send_verification_email(user)
        except Exception:
            pass
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_email(request: Request) -> Response:
    """Подтверждает email по токену из письма."""
    token = request.data.get('token', '').strip()
    if not token:
        return Response({'error': 'Токен не указан.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(email_verify_token=token, email_verified=False).first()
    if not user:
        return Response(
            {'error': 'Недействительный или уже использованный токен.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Токен действителен 24 часа
    from django.utils import timezone
    if user.email_verify_sent_at:
        age = timezone.now() - user.email_verify_sent_at
        if age.total_seconds() > 86_400:
            return Response(
                {'error': 'Ссылка устарела. Запросите новое письмо.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    user.email_verified = True
    user.email_verify_token = ''
    user.save(update_fields=['email_verified', 'email_verify_token'])
    return Response({'ok': True, 'message': 'Email успешно подтверждён.'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def resend_verification(request: Request) -> Response:
    """Повторно отправляет письмо верификации."""
    user = request.user
    if user.email_verified:
        return Response({'error': 'Email уже подтверждён.'}, status=status.HTTP_400_BAD_REQUEST)

    from apps.alerts.email_notify import send_verification_email
    sent = send_verification_email(user)
    if sent:
        return Response({'ok': True, 'message': 'Письмо отправлено.'})
    # Cooldown ещё не прошёл
    return Response(
        {'error': 'Подождите несколько минут перед повторной отправкой.'},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


@ensure_csrf_cookie
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_request(request: Request) -> Response:
    """Запрос на сброс пароля по email.

    Всегда возвращает 200 с одним и тем же сообщением — чтобы не раскрывать,
    зарегистрирован ли email в системе.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    email = request.data.get('email', '').strip()
    generic = {'ok': True, 'message': 'Если такой email зарегистрирован, мы отправили ссылку для сброса.'}
    if not email:
        return Response({'error': 'Укажите email.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user:
        from django.conf import settings as dj_settings
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        site = getattr(dj_settings, 'SITE_URL', '').rstrip('/') or 'http://localhost'
        reset_url = f'{site}/reset-password?uid={uid}&token={token}'
        try:
            from apps.alerts.email_notify import send_password_reset_email
            send_password_reset_email(user, reset_url)
        except Exception:
            logger.exception('Password reset email failed for %s', email)

    return Response(generic)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_confirm(request: Request) -> Response:
    """Устанавливает новый пароль по uid + token из письма."""
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    uid = request.data.get('uid', '')
    token = request.data.get('token', '')
    password = request.data.get('password', '')
    password_confirm = request.data.get('password_confirm', '')

    if not uid or not token:
        return Response({'error': 'Недействительная ссылка.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(password) < 8:
        return Response({'error': 'Пароль должен быть не короче 8 символов.'}, status=status.HTTP_400_BAD_REQUEST)
    if password != password_confirm:
        return Response({'error': 'Пароли не совпадают.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return Response(
            {'error': 'Ссылка недействительна или устарела. Запросите сброс заново.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(password)
    user.save(update_fields=['password'])
    return Response({'ok': True, 'message': 'Пароль изменён. Теперь войдите с новым паролем.'})


@ensure_csrf_cookie
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
    # Форма логина допускает ввод email — если по username не вышло
    # и это похоже на email, ищем пользователя по почте.
    if user is None and '@' in username:
        match = User.objects.filter(email__iexact=username).first()
        if match:
            user = authenticate(request, username=match.username, password=password)
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


@ensure_csrf_cookie
@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def me_view(request: Request) -> Response:
    user = request.user
    if request.method == 'PATCH':
        # Разрешаем менять только безопасные поля профиля и настройки уведомлений.
        allowed = {'first_name', 'last_name', 'notify_telegram', 'notify_email'}
        fields = []
        for key in allowed:
            if key in request.data:
                setattr(user, key, request.data[key])
                fields.append(key)
        if fields:
            user.save(update_fields=fields)
    return Response(UserSerializer(user).data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def telegram_link(request: Request) -> Response:
    """Генерирует код привязки Telegram и возвращает инструкцию для пользователя."""
    from django.conf import settings
    from apps.alerts.telegram import generate_link_code, is_configured

    if not is_configured():
        return Response(
            {'error': 'Telegram-интеграция отключена на сервере.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    code = generate_link_code(request.user)
    bot = settings.TELEGRAM_BOT_USERNAME
    deep_link = f'https://t.me/{bot}?start={code}' if bot else None
    return Response({
        'code': code,
        'bot_username': bot,
        'deep_link': deep_link,
        'instructions': (
            f'Откройте бота @{bot} в Telegram и отправьте: /start {code}'
            if bot else
            f'Отправьте боту сообщение: /start {code}'
        ),
        'expires_in_minutes': settings.TELEGRAM_LINK_CODE_TTL_MINUTES,
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def telegram_status(request: Request) -> Response:
    user = request.user
    return Response({
        'linked': user.telegram_linked,
        'telegram_username': user.telegram_username,
        'notify_telegram': user.notify_telegram,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def telegram_unlink(request: Request) -> Response:
    user = request.user
    user.telegram_chat_id = ''
    user.telegram_username = ''
    user.telegram_link_code = ''
    user.telegram_link_expires_at = None
    user.telegram_linked_at = None
    user.notify_telegram = False
    user.save(update_fields=[
        'telegram_chat_id', 'telegram_username', 'telegram_link_code',
        'telegram_link_expires_at', 'telegram_linked_at', 'notify_telegram',
    ])
    return Response({'linked': False})


class BuildViewSet(viewsets.ViewSet):
    """Сборка ПК пользователя. Зеркалит логику фронтового конструктора, но на бэке.

    Один «текущий» build на пользователя (get_or_create). Слоты — uniquе по build+slot.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_build(self, request: Request):
        from apps.builds.models import Build

        build, _ = Build.objects.get_or_create(user=request.user)
        return build

    @action(detail=False, methods=['get'])
    def me(self, request: Request) -> Response:
        from .serializers import BuildSerializer

        build = self._get_build(request)
        return Response(BuildSerializer(build).data)

    @action(detail=False, methods=['post'], url_path='set-slot')
    def set_slot(self, request: Request) -> Response:
        from apps.builds.models import BuildItem
        from .serializers import BuildSerializer

        build = self._get_build(request)
        slot = request.data.get('slot')
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        valid_slots = {c[0] for c in BuildItem.Slot.choices}
        if slot not in valid_slots:
            return Response({'error': 'Неизвестный слот.'}, status=status.HTTP_400_BAD_REQUEST)
        if not product_id:
            return Response({'error': 'product_id обязателен.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Товар не найден.'}, status=status.HTTP_404_NOT_FOUND)

        # Snapshot текущей лучшей цены на момент добавления (денормализованная Offer.current_price).
        best = (
            Offer.objects
            .filter(product=product, current_price__gt=0)
            .order_by('current_price')
            .first()
        )
        price_snapshot = best.current_price if best else 0

        BuildItem.objects.update_or_create(
            build=build, slot=slot,
            defaults={'product': product, 'price_snapshot': price_snapshot, 'quantity': quantity},
        )
        build.save(update_fields=['updated_at'])
        return Response(BuildSerializer(build).data)

    @action(detail=False, methods=['delete'], url_path='clear-slot/(?P<slot>[^/.]+)')
    def clear_slot(self, request: Request, slot: str | None = None) -> Response:
        from apps.builds.models import BuildItem
        from .serializers import BuildSerializer

        build = self._get_build(request)
        BuildItem.objects.filter(build=build, slot=slot).delete()
        build.save(update_fields=['updated_at'])
        return Response(BuildSerializer(build).data)

    @action(detail=False, methods=['post'])
    def clear(self, request: Request) -> Response:
        from .serializers import BuildSerializer

        build = self._get_build(request)
        build.items.all().delete()
        build.save(update_fields=['updated_at'])
        return Response(BuildSerializer(build).data)
