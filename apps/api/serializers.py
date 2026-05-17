from decimal import Decimal

from rest_framework import serializers

from apps.alerts.models import Notification, Subscription
from apps.analytics.models import Anomaly
from apps.prices.models import PriceHistory
from apps.products.models import Category, CategoryListing, Offer, Product


class CategoryListingSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = CategoryListing
        fields = ('id', 'source', 'source_display', 'external_path', 'is_active')


class CategorySerializer(serializers.ModelSerializer):

    store_listings = CategoryListingSerializer(source='listings', many=True, read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'is_active', 'store_listings')


class PriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceHistory
        fields = ('id', 'price', 'old_price', 'timestamp', 'is_actual', 'source')


def _current_price_for_offer(offer: Offer) -> Decimal | None:
    record = (
        PriceHistory.objects
        .filter(offer=offer, is_actual=True)
        .order_by('-timestamp')
        .first()
    )
    return record.price if record else None


class OfferSerializer(serializers.ModelSerializer):

    source_display = serializers.CharField(source='get_source_display', read_only=True)
    current_price = serializers.SerializerMethodField()
    old_price = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = (
            'id', 'source', 'source_display', 'url', 'vendor_code', 'image_url',
            'is_available', 'last_seen_at', 'current_price', 'old_price',
        )

    def get_current_price(self, obj: Offer) -> str | None:
        price = _current_price_for_offer(obj)
        return str(price) if price is not None else None

    def get_old_price(self, obj: Offer) -> str | None:
        record = (
            PriceHistory.objects
            .filter(offer=obj, is_actual=True)
            .order_by('-timestamp')
            .first()
        )
        return str(record.old_price) if record and record.old_price else None


def _best_offer_summary(product: Product) -> dict | None:
    actual = (
        PriceHistory.objects
        .filter(product=product, is_actual=True, offer__isnull=False)
        .select_related('offer')
        .order_by('price')
    )
    best = actual.first()
    if not best or not best.offer:
        legacy = (
            PriceHistory.objects
            .filter(product=product, is_actual=True)
            .order_by('price')
            .first()
        )
        if not legacy:
            return None
        return {
            'price': str(legacy.price),
            'source': legacy.source,
            'source_display': dict(PriceHistory.Source.choices).get(legacy.source, legacy.source),
            'url': product.url,
            'offers_count': 0,
        }
    return {
        'price': str(best.price),
        'source': best.offer.source,
        'source_display': best.offer.get_source_display(),
        'url': best.offer.url,
        'offers_count': product.offers.count(),
    }


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    best_offer = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'category', 'vendor_code',
            'image_url', 'is_active', 'last_parsed_at', 'best_offer',
        )

    def get_best_offer(self, obj: Product) -> dict | None:
        return _best_offer_summary(obj)


class ProductDetailSerializer(ProductListSerializer):
    offers = serializers.SerializerMethodField()
    price_history = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ('offers', 'price_history', 'url')

    def get_offers(self, obj: Product) -> list[dict]:
        offers = obj.offers.all().order_by('source')
        return OfferSerializer(offers, many=True).data

    def get_price_history(self, obj: Product) -> list[dict]:
        recent = (
            PriceHistory.objects
            .filter(product=obj)
            .order_by('-timestamp')[:300]
        )
        return PriceHistorySerializer(recent, many=True).data


class SubscriptionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Subscription
        fields = ('id', 'product', 'product_name', 'target_price', 'is_active', 'created_at')
        read_only_fields = ('is_active', 'created_at')

    def validate_product(self, value: Product) -> Product:
        user = self.context['request'].user
        if Subscription.objects.filter(user=user, product=value).exists():
            raise serializers.ValidationError('Подписка на этот товар уже существует.')
        return value

    def create(self, validated_data: dict) -> Subscription:
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'message', 'sent_at')


class AnomalySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Anomaly
        fields = (
            'id', 'product', 'product_name', 'anomaly_type',
            'severity', 'description', 'detected_at', 'resolved',
        )
