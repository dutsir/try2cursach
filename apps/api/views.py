import logging

from django.contrib.auth import authenticate, login, logout
from django.db.models import (
    BooleanField, Count, DecimalField, Exists, ExpressionWrapper, F,
    Max, Min, OuterRef, Q, Subquery, Value,
)
from django.views.decorators.csrf import csrf_exempt
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
from apps.products.models import Category, Offer, Product, ProductFamily

logger = logging.getLogger(__name__)

from .serializers import (
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
        return queryset.filter(
            offers__price_history__is_actual=True,
            offers__price_history__price__gte=value,
        ).distinct()

    def filter_max_price(self, queryset, name, value):
        return queryset.filter(
            offers__price_history__is_actual=True,
            offers__price_history__price__lte=value,
        ).distinct()

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
        .filter(Exists(Offer.objects.filter(product=OuterRef('pk'))))
        .select_related('category')
        .prefetch_related('offers', 'category__listings')
    )
    permission_classes = [permissions.AllowAny]
    filterset_class = ProductFilterSet
    search_fields = ['name', 'vendor_code']
    ordering_fields = ['name', 'last_parsed_at', 'created_at', 'min_price']

    def get_queryset(self):
        qs = super().get_queryset()
        # Annotate min_price для сортировки по цене (берём минимум по актуальным записям)
        if 'min_price' in (self.request.query_params.get('ordering') or ''):
            qs = qs.annotate(
                min_price=Min(
                    'offers__price_history__price',
                    filter=Q(offers__price_history__is_actual=True),
                )
            )
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

    @action(detail=True, methods=['get'], url_path='offers')
    def offers(self, request: Request, pk: int | None = None) -> Response:
        product = self.get_object()
        offers = product.offers.all().order_by('source')
        return Response(OfferSerializer(offers, many=True).data)

    @action(detail=True, methods=['get'], url_path='price-stats')
    def price_stats(self, request: Request, pk: int | None = None) -> Response:
        """Возвращает агрегаты PriceStats: за всё время, 30д, 7д.

        current_price берётся как минимальная цена среди доступных офферов
        (зеркало логики в шаблоне catalog/product.html).
        """
        product = self.get_object()

        # current_price: best price среди ПОСЛЕДНИХ актуальных записей по каждому
        # офферу. Цена хранится в PriceHistory, а не в Offer.
        offers = list(product.offers.all())
        offer_prices: list[tuple[int, bool]] = []  # (price, is_available)
        for offer in offers:
            last = (
                PriceHistory.objects
                .filter(offer=offer, is_actual=True)
                .only('price')
                .order_by('-timestamp')
                .first()
            )
            if last and last.price and last.price > 0:
                offer_prices.append((int(last.price), bool(offer.is_available)))

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

        # Price range — из последних is_actual PriceHistory
        price_agg = (
            PriceHistory.objects
            .filter(product__in=products, is_actual=True, price__gt=0)
            .aggregate(min_price=Min('price'), max_price=Max('price'))
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
            'products': Product.objects.filter(is_active=True).count(),
            'categories': Category.objects.filter(is_active=True).count(),
            'offers': Offer.objects.count(),
            'price_records_24h': PriceHistory.objects.filter(timestamp__gte=since_24h).count(),
        }

        # === Top deals: товары с актуальной скидкой (old_price > price) ===
        # Берём актуальные PriceHistory с old_price, сортируем по % скидки
        deals_qs = (
            PriceHistory.objects
            .filter(is_actual=True, old_price__gt=F('price'), price__gt=0, offer__isnull=False)
            .select_related('product', 'offer', 'product__category')
            .annotate(
                discount_pct=ExpressionWrapper(
                    (F('old_price') - F('price')) * 100.0 / F('old_price'),
                    output_field=DecimalField(max_digits=5, decimal_places=2),
                )
            )
            .order_by('-discount_pct')[:30]
        )
        # Дедупликация по product чтобы один товар не повторялся
        seen_products = set()
        top_deals = []
        for ph in deals_qs:
            if ph.product_id in seen_products:
                continue
            seen_products.add(ph.product_id)
            top_deals.append({
                'id': ph.product_id,
                'name': ph.product.name,
                'slug': ph.product.slug,
                'brand': ph.product.brand,
                'category_name': ph.product.category.name if ph.product.category else '',
                'image_url': ph.offer.image_url or ph.product.image_url or '',
                'price': str(ph.price),
                'old_price': str(ph.old_price),
                'discount_pct': int(ph.discount_pct or 0),
                'source': ph.offer.source,
                'source_display': ph.offer.get_source_display(),
                'url': ph.offer.url,
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
            last = (
                PriceHistory.objects
                .filter(offer=o, is_actual=True)
                .order_by('-timestamp')
                .first()
            )
            if last and last.price:
                offers_by_source[o.source] = {
                    'price': str(last.price),
                    'old_price': str(last.old_price) if last.old_price else None,
                    'source_display': o.get_source_display(),
                    'url': o.url,
                    'image_url': o.image_url or p.image_url or '',
                    'is_available': o.is_available,
                    'rating': o.extra_metadata.get('supplier_rating') if o.extra_metadata else None,
                    'reviews_count': o.extra_metadata.get('reviews_count') if o.extra_metadata else None,
                }

                if best_price is None or last.price < best_price:
                    best_price = last.price
                    best_offer = (o, last)

        price_trend = None
        if best_offer:
            o, last = best_offer
            thirty_days_ago = timezone.now() - timedelta(days=30)
            old_price_record = (
                PriceHistory.objects
                .filter(offer=o, timestamp__lte=thirty_days_ago)
                .order_by('-timestamp')
                .first()
            )
            if old_price_record and old_price_record.price:
                delta = float(last.price - old_price_record.price)
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
            o, _ = best_offer
            if o.normalized_features:
                specs_dict.update(o.normalized_features)
            if o.extra_metadata:
                for k, v in o.extra_metadata.items():
                    if k not in ['rating', 'supplier_rating', 'reviews_count', 'sale_percent', 'cashback_percent', 'supplier']:
                        specs_dict[k] = v

        stats = {}
        if best_offer:
            o, _ = best_offer
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
            o, last = best_offer
            best_info = {
                'price': str(last.price),
                'old_price': str(last.old_price) if last.old_price else None,
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


class OfferViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Offer.objects.select_related('product', 'product__category').all()
    serializer_class = OfferSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['source', 'product', 'product__category__slug', 'is_available']
    search_fields = ['product__name', 'vendor_code']
    ordering_fields = ['last_seen_at', 'source']


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


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


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
