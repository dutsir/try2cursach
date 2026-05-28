from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel


from pgvector.django import HnswIndex, VectorField

EMBEDDING_DIM = int(getattr(settings, 'DEDUP_EMBEDDING_DIM', 768))


class Category(BaseModel):

    name = models.CharField('Название', max_length=255)
    slug = models.SlugField('Слаг', max_length=255, unique=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская категория',
    )
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']
        indexes = [
            models.Index(fields=['parent', 'is_active']),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def store_path(self, source: str) -> str:
        lst = self.listings.filter(source=source, is_active=True).first()
        if not lst:
            return ''
        return (lst.external_path or '').strip()

    @property
    def is_leaf(self) -> bool:
        return not self.children.exists()

    def ancestors(self) -> list['Category']:
        chain: list[Category] = []
        node = self.parent

        for _ in range(10):
            if node is None:
                break
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def descendants_ids(self) -> list[int]:
        ids: list[int] = [self.pk]
        stack: list[int] = [self.pk]

        for _ in range(10):
            if not stack:
                break
            children_ids = list(
                Category.objects.filter(parent_id__in=stack).values_list('id', flat=True)
            )
            if not children_ids:
                break
            ids.extend(children_ids)
            stack = children_ids
        return ids


class CategoryListing(BaseModel):

    class Source(models.TextChoices):
        DNS = 'dns', 'DNS'
        CITILINK = 'citilink', 'Ситилинк'
        OZON = 'ozon', 'Ozon'
        WB = 'wb', 'Wildberries'
        REGARD = 'regard', 'Регард'

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='listings',
        verbose_name='Категория',
    )
    source = models.CharField('Магазин', max_length=32, choices=Source.choices, db_index=True)
    external_path = models.CharField(
        'Каталог у магазина',
        max_length=1024,
        help_text=(
            'DNS: slug вида 17a89aab16404e77/videokarty. '
            'Ситилинк: относительный путь или полный URL каталога. '
            'Ozon: полный URL раздела (без обязательной валидации URL — допускаются длинные пути).'
        ),
    )
    is_active = models.BooleanField('Учитывать при парсинге', default=True)

    class Meta:
        verbose_name = 'Каталог у магазина'
        verbose_name_plural = 'Каталоги у магазинов'
        ordering = ['category_id', 'source']
        constraints = [
            models.UniqueConstraint(fields=['category', 'source'], name='category_listing_source_unique'),
        ]
        indexes = [
            models.Index(fields=['source', 'is_active']),
        ]

    def __str__(self) -> str:
        return f'{self.category.slug} @ {self.get_source_display()}'


class ProductFamily(BaseModel):
    """Семейство товаров — линейка/модель, объединяющая варианты конфигураций.

    Один ноутбук «Lenovo ThinkPad X1 Carbon Gen 11» — это семейство; вариации
    по RAM/SSD/цвету — отдельные Product со ссылкой на эту семью.
    """

    name = models.CharField('Название семейства', max_length=512)
    brand = models.CharField('Бренд', max_length=64, blank=True, default='', db_index=True)
    model_code = models.CharField(
        'Модельный код', max_length=128, blank=True, default='',
        help_text='Канонический код модели без указания поколения (например, "X1 Carbon").',
    )
    generation = models.CharField(
        'Поколение', max_length=64, blank=True, default='',
        help_text='Поколение/ревизия модели (например, "Gen 11", "M3").',
    )
    year = models.PositiveSmallIntegerField('Год', null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='families',
        verbose_name='Категория',
    )
    common_specs = models.JSONField(
        'Общие характеристики', default=dict, blank=True,
        help_text='Specs, общие для всех вариантов семьи (cpu_family, gpu_family, screen_in и т. п.).',
    )
    family_key_hash = models.CharField(
        'Хэш семейного ключа', max_length=40, blank=True, default='', db_index=True,
    )
    match_embedding = VectorField(
        'Embedding для матчинга семьи',
        dimensions=EMBEDDING_DIM,
        null=True, blank=True,
        help_text='Вектор по «семейному» названию без варьируемых полей.',
    )
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Семейство товаров'
        verbose_name_plural = 'Семейства товаров'
        ordering = ['brand', 'model_code', 'generation']
        indexes = [
            models.Index(fields=['brand', 'category']),
            models.Index(fields=['family_key_hash']),
            GinIndex(fields=['common_specs'], name='family_common_specs_gin'),
            HnswIndex(
                name='family_match_embedding_hnsw',
                fields=['match_embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Product(BaseModel):

    name = models.CharField('Название', max_length=512)
    slug = models.SlugField('Слаг', max_length=512, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='Категория',
    )
    family = models.ForeignKey(
        ProductFamily,
        on_delete=models.SET_NULL,
        related_name='variants',
        verbose_name='Семейство',
        null=True, blank=True,
    )
    vendor_code = models.CharField(
        'Артикул (MPN)', max_length=100, blank=True, default='', db_index=True,
    )


    brand = models.CharField(
        'Бренд', max_length=64, blank=True, default='', db_index=True,
    )


    specs_fingerprint = models.JSONField(
        'Структурированные характеристики',
        default=dict, blank=True,
    )

    variant_specs = models.JSONField(
        'Характеристики варианта', default=dict, blank=True,
        help_text='Specs, отличающие данный вариант внутри семьи (ram_gb, storage_gb, color).',
    )

    variant_key_hash = models.CharField(
        'Хэш варианта внутри семьи', max_length=40, blank=True, default='', db_index=True,
    )


    key_hash = models.CharField(
        'Хэш матчинг-ключа', max_length=40, blank=True, default='', db_index=True,
    )


    merge_locked = models.BooleanField(
        'Запретить автоматический merge', default=False,
    )


    match_embedding = VectorField(
        'Embedding для матчинга',
        dimensions=EMBEDDING_DIM,
        null=True,
        blank=True,
        help_text='Вектор sentence-transformers для cross-source semantic match',
    )
    url = models.URLField('URL карточки товара', max_length=1024)
    image_url = models.URLField('URL изображения', max_length=1024, blank=True, default='')
    is_active = models.BooleanField('Активен', default=True)
    last_parsed_at = models.DateTimeField('Последний парсинг', null=True, blank=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-last_parsed_at']
        constraints = [


            models.UniqueConstraint(
                fields=['category', 'brand', 'vendor_code'],
                condition=models.Q(vendor_code__gt='') & models.Q(brand__gt=''),
                name='product_brand_mpn_in_category_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['brand', 'category']),
            models.Index(fields=['key_hash']),
            models.Index(fields=['family', 'variant_key_hash']),
            GinIndex(fields=['specs_fingerprint'], name='product_specs_fingerprint_gin'),


            HnswIndex(
                name='product_match_embedding_hnsw',
                fields=['match_embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            base = slugify(self.name, allow_unicode=True)[:480]
            self.slug = f'{base}-{self.vendor_code}' if self.vendor_code else base
        super().save(*args, **kwargs)


class Offer(BaseModel):

    class Source(models.TextChoices):
        DNS = 'dns', 'DNS'
        OZON = 'ozon', 'Ozon'
        CITILINK = 'citilink', 'Ситилинк'
        WB = 'wb', 'Wildberries'
        REGARD = 'regard', 'Регард'

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='offers',
        verbose_name='Мастер-товар',
    )
    source = models.CharField(
        'Магазин', max_length=32, choices=Source.choices, db_index=True,
    )
    url = models.URLField('URL оффера', max_length=1024)


    source_sku = models.CharField(
        'Артикул магазина (shop SKU)', max_length=128, blank=True, default='', db_index=True,
    )
    vendor_code = models.CharField(
        'Артикул в магазине', max_length=128, blank=True, default='', db_index=True,
    )


    mpn_extracted = models.CharField(
        'Извлечённый MPN', max_length=64, blank=True, default='', db_index=True,
    )

    raw_name = models.TextField('Исходное имя у магазина', blank=True, default='')


    normalized_features = models.JSONField(
        'Нормализованные фичи', default=dict, blank=True,
    )

    match_signals = models.JSONField(
        'Сигналы матчинга', default=dict, blank=True,
    )


    confidence = models.DecimalField(
        'Уверенность матчинга', max_digits=3, decimal_places=2,
        default=0, blank=True,
    )
    image_url = models.URLField('Картинка оффера', max_length=1024, blank=True, default='')
    is_available = models.BooleanField('В наличии', default=True)
    last_seen_at = models.DateTimeField('Последний успешный парсинг', null=True, blank=True)

    extra_metadata = models.JSONField(
        'Доп. метаданные источника',
        default=dict, blank=True,
        help_text=(
            'Поля специфичные для источника: rating, reviews_count, brand, '
            'brand_id, sale_percent, cashback_percent, supplier и т.д.'
        ),
    )

    class Meta:
        verbose_name = 'Оффер'
        verbose_name_plural = 'Офферы'
        ordering = ['source', '-last_seen_at']
        constraints = [
            models.UniqueConstraint(fields=['source', 'url'], name='offer_source_url_unique'),


            models.UniqueConstraint(
                fields=['source', 'source_sku'],
                condition=models.Q(source_sku__gt=''),
                name='offer_source_sku_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'source']),
            models.Index(fields=['source', 'mpn_extracted']),
        ]

    def __str__(self) -> str:
        return f'{self.get_source_display()}: {self.product.name}'


class MergeAuditLog(BaseModel):

    class Actor(models.TextChoices):
        AUTO = 'auto', 'Автоматический матчер'
        MANUAL = 'manual', 'Ручная правка админа'
        MIGRATION = 'migration', 'Миграция/rebuild'
        SHADOW = 'shadow', 'Shadow-прогон (без изменений в БД)'

    class Decision(models.TextChoices):
        AUTO_MERGE = 'auto_merge', 'Автоматический merge'
        REVIEW = 'review', 'Создан новый, кандидат в очередь review'
        NEW = 'new', 'Создан новый Product'
        UPDATE = 'update', 'Обновление существующего оффера'

    offer = models.ForeignKey(
        'Offer', on_delete=models.SET_NULL,
        related_name='merge_audit',
        verbose_name='Оффер',
        null=True, blank=True,
    )
    from_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        related_name='merge_audit_from',
        verbose_name='Старый мастер-товар',
        null=True, blank=True,
    )
    to_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        related_name='merge_audit_to',
        verbose_name='Новый мастер-товар',
        null=True, blank=True,
    )
    actor = models.CharField('Кто принял решение', max_length=16, choices=Actor.choices)
    decision = models.CharField('Решение', max_length=16, choices=Decision.choices)
    score = models.DecimalField(
        'Score кандидата', max_digits=4, decimal_places=3,
        default=0, blank=True,
    )
    signals = models.JSONField('Сигналы матчинга', default=dict, blank=True)


    run_id = models.CharField('ID прогона', max_length=64, blank=True, default='', db_index=True)
    reverted = models.BooleanField('Откачено', default=False)

    class Meta:
        verbose_name = 'Запись аудита матчинга'
        verbose_name_plural = 'Аудит матчинга'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['actor', '-created_at']),
            models.Index(fields=['decision', '-created_at']),
            models.Index(fields=['offer', '-created_at']),
        ]

    def __str__(self) -> str:
        from_id = self.from_product_id or '—'
        to_id = self.to_product_id or '—'
        return f'[{self.actor}] {self.decision}: {from_id}→{to_id} score={self.score}'


class MatchReview(BaseModel):

    class Status(models.TextChoices):
        PENDING = 'pending', 'В ожидании'
        APPROVED = 'approved', 'Одобрено'
        REJECTED = 'rejected', 'Отклонено'

    offer = models.ForeignKey(
        'Offer', on_delete=models.CASCADE,
        related_name='match_reviews',
        verbose_name='Оффер',
    )
    suggested_product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='match_reviews',
        verbose_name='Предложенный мастер-товар',
    )
    score = models.DecimalField(
        'Score', max_digits=4, decimal_places=3,
        default=0,
    )
    signals = models.JSONField('Сигналы матчинга', default=dict, blank=True)
    status = models.CharField(
        'Статус', max_length=16, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='match_decisions',
        verbose_name='Кто принял решение',
    )
    decided_at = models.DateTimeField('Когда решено', null=True, blank=True)
    note = models.CharField('Комментарий', max_length=512, blank=True, default='')

    class Meta:
        verbose_name = 'Заявка на ручной матчинг'
        verbose_name_plural = 'Очередь ручного матчинга'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]
        constraints = [


            models.UniqueConstraint(
                fields=['offer', 'suggested_product'],
                name='match_review_offer_suggested_unique',
            ),
        ]

    def __str__(self) -> str:
        return f'review[{self.status}] offer={self.offer_id} → product={self.suggested_product_id}'
