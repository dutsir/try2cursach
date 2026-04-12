import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

from celery import chain, shared_task
from django.conf import settings
from django.utils import timezone

from apps.products.models import Category, Product
from apps.products.services import get_or_create_product

logger = logging.getLogger(__name__)


def parse_category_with_parser(
    category: Category,
    parser: Any,
    *,
    sync: bool = False,
) -> dict:
    """
    Один проход по каталогу DNS и сохранение цен.

    sync=True  — цены сохраняются прямо здесь (не нужен Celery worker).
    sync=False — task_save_price уходит в очередь Celery (.delay()).

    Если парсер нашёл карточки, но не смог извлечь ни одного товара
    (признак антибот-троттлинга), браузер перезапускается и делается
    одна повторная попытка.
    """
    logger.info('Начинаем парсинг категории: %s', category.name)

    parsed_products = parser.parse_category(category.dns_category_slug)

    if not parsed_products:
        logger.warning('Парсер не вернул товаров для категории %s', category.slug)
        if sync:
            logger.info(
                'Повтор категории %s с новым браузером (возможен антибот-троттлинг)…',
                category.slug,
            )
            parser.close()
            time.sleep(8)
            parsed_products = parser.parse_category(category.dns_category_slug)
        if not parsed_products:
            return {'status': 'empty', 'category': category.slug}

    saved_count = 0
    for item in parsed_products:
        product, _ = get_or_create_product(
            category=category,
            name=item.name,
            url=item.url,
            vendor_code=item.vendor_code,
            image_url=item.image_url,
        )
        price_kwargs = dict(
            product_id=product.pk,
            price=item.price,
            old_price=item.old_price,
            timestamp=timezone.now().isoformat(),
        )
        if sync:
            task_save_price(**price_kwargs)
        else:
            task_save_price.delay(**price_kwargs)
        saved_count += 1

    logger.info(
        'Категория %s: спарсено %d, сохранено/поставлено задач цен: %d',
        category.slug, len(parsed_products), saved_count,
    )
    return {'status': 'ok', 'category': category.slug, 'parsed': len(parsed_products)}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
    acks_late=True,
)
def task_parse_category(self, category_id: int) -> dict:
    from .parsers import DNSParser

    try:
        category = Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist:
        logger.warning('Категория id=%d не найдена или неактивна', category_id)
        return {'status': 'skipped', 'reason': 'category_not_found'}

    with DNSParser() as parser:
        return parse_category_with_parser(category, parser)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,
    retry_backoff_max=120,
    max_retries=5,
)
def task_save_price(
    self,
    product_id: int,
    price: int,
    old_price: int | None = None,
    timestamp: str | None = None,
) -> dict:
    from .models import PriceHistory

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        logger.warning('Товар id=%d не найден', product_id)
        return {'status': 'skipped'}

    ts = datetime.fromisoformat(timestamp) if timestamp else timezone.now()

    last_record = (
        PriceHistory.objects
        .filter(product=product, is_actual=True)
        .order_by('-timestamp')
        .first()
    )

    price_decimal = Decimal(str(price))
    old_price_decimal = Decimal(str(old_price)) if old_price else None

    if last_record and last_record.price == price_decimal:
        logger.debug('Цена товара %s не изменилась (%s₽)', product.name, price_decimal)
        return {'status': 'unchanged', 'product_id': product_id}

    if last_record:
        last_record.is_actual = False
        last_record.save(update_fields=['is_actual', 'updated_at'])

    PriceHistory.objects.create(
        product=product,
        price=price_decimal,
        old_price=old_price_decimal,
        timestamp=ts,
        is_actual=True,
        source=PriceHistory.Source.DNS,
    )

    logger.info('Сохранена цена для %s: %s₽', product.name, price_decimal)

    from apps.analytics.tasks import task_detect_anomalies
    task_detect_anomalies.delay(product_id=product.pk)

    return {'status': 'saved', 'product_id': product_id, 'price': str(price_decimal)}


@shared_task
def task_pause_between_dns_categories(seconds: int) -> None:
    if seconds > 0:
        time.sleep(seconds)


@shared_task
def task_parse_all_categories() -> dict:
    categories = list(Category.objects.filter(is_active=True).order_by('id'))
    count = len(categories)
    if count == 0:
        return {'queued': 0}

    pause = int(getattr(settings, 'CELERY_DNS_CATEGORY_PAUSE_SECONDS', 0) or 0)

    if pause <= 0:
        for cat in categories:
            task_parse_category.delay(cat.pk)
        logger.info('Поставлено задач парсинга для %d категорий (без пауз между ними)', count)
        return {'queued': count, 'stagger': False}

    links: list[Any] = []
    for i, cat in enumerate(categories):
        links.append(task_parse_category.si(cat.pk))
        if i < count - 1:
            links.append(task_pause_between_dns_categories.si(pause))

    chain(*links).apply_async()
    logger.info(
        'Запущена цепочка парсинга %d категорий с паузой %d с между категориями',
        count,
        pause,
    )
    return {'queued': count, 'stagger': True, 'pause_seconds': pause}
