from rest_framework import serializers

from apps.alerts.models import Notification, Subscription, Wishlist, WishlistItem
from apps.core.models import User
from apps.prices.models import PriceHistory
from apps.products.models import Category, CategoryListing, Offer, Product


class CategoryListingSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = CategoryListing
        fields = ('id', 'source', 'source_display', 'external_path', 'is_active')


class CategoryMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


class CategorySerializer(serializers.ModelSerializer):

    store_listings = CategoryListingSerializer(source='listings', many=True, read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'is_active', 'store_listings')


class PriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceHistory
        fields = ('id', 'price', 'old_price', 'timestamp', 'is_actual', 'source')


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

    def _fallback_price_payload(self, obj: Offer) -> dict | None:
        by_offer = self.context.get('fallback_price_by_offer') or {}
        by_source = self.context.get('fallback_price_by_source') or {}
        return by_offer.get(obj.id) or by_source.get(obj.source)

    def get_current_price(self, obj: Offer) -> str | None:
        if obj.current_price is not None:
            return str(obj.current_price)
        fallback = self._fallback_price_payload(obj)
        return fallback['price'] if fallback else None

    def get_old_price(self, obj: Offer) -> str | None:
        if obj.current_old_price:
            return str(obj.current_old_price)
        fallback = self._fallback_price_payload(obj)
        return fallback['old_price'] if fallback else None


def _preferred_image_from_offers(offers: list[Offer]) -> str:
    preferred_sources = (
        Offer.Source.DNS,
        Offer.Source.CITILINK,
        Offer.Source.MVIDEO,
    )
    for source in preferred_sources:
        image_url = next((o.image_url for o in offers if o.source == source and o.image_url), '')
        if image_url:
            return image_url
    return next((o.image_url for o in offers if o.image_url), '')


def _build_offer_price_fallbacks(product: Product, offers: list[Offer]) -> tuple[dict[int, dict], dict[str, dict]]:
    offer_ids = [o.id for o in offers]
    by_offer: dict[int, dict] = {}
    by_source: dict[str, dict] = {}

    if offer_ids:
        latest_by_offer = (
            PriceHistory.objects
            .filter(offer_id__in=offer_ids, is_actual=True)
            .order_by('offer_id', '-timestamp')
            .distinct('offer_id')
            .values('offer_id', 'price', 'old_price')
        )
        by_offer = {
            row['offer_id']: {
                'price': str(row['price']),
                'old_price': str(row['old_price']) if row['old_price'] else None,
            }
            for row in latest_by_offer
        }

    latest_by_source = (
        PriceHistory.objects
        .filter(product=product, is_actual=True)
        .order_by('source', '-timestamp')
        .distinct('source')
        .values('source', 'price', 'old_price')
    )
    by_source = {
        row['source']: {
            'price': str(row['price']),
            'old_price': str(row['old_price']) if row['old_price'] else None,
        }
        for row in latest_by_source
    }
    return by_offer, by_source


def _best_offer_summary(product: Product) -> dict | None:
    # Читаем денормализованную Offer.current_price — без N+1 по PriceHistory.
    # Если префетч offers есть, перебираем в памяти; иначе один запрос на оффер с ценой.
    all_offers = list(product.offers.all())
    offers = [o for o in all_offers if o.current_price is not None]
    if offers:
        best = min(offers, key=lambda o: o.current_price)
        # Приоритет качества изображений для карточек:
        # DNS -> Ситилинк -> М.Видео -> остальные источники.
        preferred_image_url = _preferred_image_from_offers(all_offers)
        image_url = preferred_image_url or best.image_url or product.image_url or ''
        if not image_url:
            image_url = _preferred_image_from_offers(all_offers)
        return {
            'price': str(best.current_price),
            'old_price': str(best.current_old_price) if best.current_old_price else None,
            'source': best.source,
            'source_display': best.get_source_display(),
            'url': best.url,
            'image_url': image_url,
            'offers_count': len(all_offers),
        }

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
        'old_price': str(legacy.old_price) if legacy.old_price else None,
        'source': legacy.source,
        'source_display': dict(PriceHistory.Source.choices).get(legacy.source, legacy.source),
        'url': product.url,
        'image_url': product.image_url or '',
        'offers_count': 0,
    }


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    best_offer = serializers.SerializerMethodField()
    is_price_min = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'brand', 'category', 'vendor_code',
            'image_url', 'is_active', 'last_parsed_at', 'best_offer', 'is_price_min',
        )

    def get_best_offer(self, obj: Product) -> dict | None:
        return _best_offer_summary(obj)

    def get_is_price_min(self, obj: Product) -> bool | None:
        # Заполняется только когда queryset аннотирован (фильтр at_historical_min);
        # в обычном каталоге аннотаций нет → None (фронт бейдж не рисует).
        hist = getattr(obj, 'hist_min', None)
        cur = getattr(obj, 'cur_min', None)
        if hist is None or cur is None:
            return None
        return cur <= hist


class ProductDetailSerializer(ProductListSerializer):
    offers = serializers.SerializerMethodField()
    family = serializers.SerializerMethodField()
    variant_specs = serializers.JSONField(read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            'offers', 'url', 'family', 'variant_specs',
        )

    def get_offers(self, obj: Product) -> list[dict]:
        offers = list(obj.offers.all().order_by('source'))
        fallback_by_offer, fallback_by_source = _build_offer_price_fallbacks(obj, offers)
        context = {
            **self.context,
            'fallback_price_by_offer': fallback_by_offer,
            'fallback_price_by_source': fallback_by_source,
        }
        return OfferSerializer(offers, many=True, context=context).data

    def get_family(self, obj: Product) -> dict | None:
        f = obj.family
        if f is None:
            return None
        return {'id': f.id, 'name': f.name, 'variants_count': f.variants.count()}


class SubscriptionSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Subscription
        fields = (
            'id', 'product', 'product_id', 'target_price',
            'notify_on', 'is_active', 'last_notified_at', 'created_at',
        )
        read_only_fields = ('created_at', 'last_notified_at')

    def validate_product_id(self, value: int) -> int:
        user = self.context['request'].user
        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError('Товар не найден.')
        if Subscription.objects.filter(user=user, product_id=value).exists():
            raise serializers.ValidationError('Подписка на этот товар уже существует.')
        return value

    def create(self, validated_data: dict) -> Subscription:
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True, allow_null=True)
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = Notification
        fields = ('id', 'type', 'message', 'is_read', 'product_id', 'product_name', 'sent_at')
        # Через API клиент может менять только is_read (пометка прочитанным).
        read_only_fields = ('type', 'message', 'product_id', 'product_name', 'sent_at')


class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = WishlistItem
        fields = ('id', 'product', 'product_id', 'quantity', 'note', 'added_at')
        read_only_fields = ('added_at',)


class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)
    total_price = serializers.FloatField(read_only=True)

    class Meta:
        model = Wishlist
        fields = ('id', 'title', 'description', 'items', 'total_price', 'created_at')


class UserSerializer(serializers.ModelSerializer):
    telegram_linked = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'avatar',
            'accepted_terms', 'notify_telegram', 'telegram_linked', 'telegram_username',
            'email_verified', 'notify_email',
        )
        read_only_fields = ('id', 'accepted_terms', 'telegram_linked', 'telegram_username', 'email_verified')


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    accepted_terms = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = (
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'accepted_terms',
        )

    def validate_accepted_terms(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError('Необходимо принять условия использования.')
        return value

    def validate(self, data: dict) -> dict:
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password': 'Пароли не совпадают.'})
        return data

    def create(self, validated_data: dict):
        from django.utils import timezone

        validated_data.pop('accepted_terms', None)
        user = User.objects.create_user(**validated_data)
        user.accepted_terms = True
        user.accepted_terms_at = timezone.now()
        user.save(update_fields=['accepted_terms', 'accepted_terms_at'])
        return user


class BuildItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        from apps.builds.models import BuildItem

        model = BuildItem
        fields = ('id', 'slot', 'product', 'price_snapshot', 'quantity')


class BuildSerializer(serializers.ModelSerializer):
    items = BuildItemSerializer(many=True, read_only=True)
    total_price = serializers.FloatField(read_only=True)

    class Meta:
        from apps.builds.models import Build

        model = Build
        fields = ('id', 'name', 'items', 'total_price', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')
