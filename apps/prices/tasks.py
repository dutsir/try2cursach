import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from celery import chain, shared_task
from django.conf import settings
from django.utils import timezone
from kombu.exceptions import OperationalError

from apps.products.models import Category, CategoryListing, Offer, Product
from apps.products.services import upsert_offer
from apps.products.dedupe.memory_optimizer import dedup_batcher

from .models import ParseRun, PriceHistory

logger = logging.getLogger(__name__)


def _persist_parsed_batch(
    category: Category,
    source: str,
    parsed_products: list,
    *,
    sync: bool,
    run: ParseRun | None = None,
) -> dict:
    saved = 0
    new_offers = 0
    new_products = 0
    saved_prices = 0

    # Для больших категорий используем батчинг, чтобы избежать OOM
    # при дедупликации (особенно важно для мониторов, материнок и т.д.)
    use_batching = len(parsed_products) > 100

    if use_batching:
        logger.info(
            'Обработка %d товаров батчами для категории %s (памяти оптимизированная обработка)',
            len(parsed_products), category.slug,
        )

        # Подготавливаем данные для батчера
        offers_data = []
        for item in parsed_products:
            offers_data.append({
                'category': category,
                'source': source,
                'name': item.name,
                'url': item.url,
                'vendor_code': item.vendor_code,
                'image_url': item.image_url,
                'is_available': getattr(item, 'is_available', True),
            })

        # Обрабатываем батчами
        batch_stats = dedup_batcher.process_offers_in_batches(
            offers_data,
            upsert_offer,
        )
        saved = batch_stats['saved']
        new_offers = batch_stats['new_offers']
        new_products = batch_stats['new_products']
    else:
        # Для маленьких категорий обычная обработка
        for item in parsed_products:
            res = upsert_offer(
                category=category,
                source=source,
                name=item.name,
                url=item.url,
                vendor_code=item.vendor_code,
                image_url=item.image_url,
                is_available=getattr(item, 'is_available', True),
            )
            saved += 1
            if res.offer_created:
                new_offers += 1
            if res.product_created:
                new_products += 1

    # Сохранение цен (после дедупликации)
    # Повторно обработаем товары для сохранения цен
    for item in parsed_products:
        try:
            offer = Offer.objects.filter(
                source=source,
                raw_name=item.name,
            ).select_related('product').first()

            if offer:
                price_kwargs = dict(
                    offer_id=offer.pk,
                    price=item.price,
                    old_price=item.old_price,
                    timestamp=timezone.now().isoformat(),
                    source=source,
                )
                if sync:
                    result = task_save_price(**price_kwargs)
                    if isinstance(result, dict) and result.get('status') == 'saved':
                        saved_prices += 1
                else:
                    task_save_price.delay(**price_kwargs)
        except Exception as exc:
            logger.debug('Ошибка при сохранении цены для %s: %s', item.name, exc)

    metrics = {
        'saved': saved,
        'new_offers': new_offers,
        'new_products': new_products,
        'saved_prices': saved_prices,
    }
    if run is not None:
        run.saved_offers = saved
        run.new_offers = new_offers
        run.new_products = new_products
        run.saved_prices = saved_prices
    return metrics


def _run_with_instrumentation(
    *,
    category: Category,
    source: str,
    sync: bool,
    parse_fn,
    log_label: str,
) -> dict:
    run = ParseRun.objects.create(
        source=source,
        category=category,
        status=ParseRun.Status.RUNNING,
    )
    logger.info('Начинаем %s: %s (run_id=%d)', log_label, category.name, run.pk)
    t0 = time.monotonic()
    try:
        parsed_products = parse_fn()
        run.parsed_count = len(parsed_products) if parsed_products else 0

        if not parsed_products:
            run.status = ParseRun.Status.EMPTY
            run.finished_at = timezone.now()
            run.save(update_fields=[
                'status', 'finished_at', 'parsed_count', 'updated_at',
            ])
            return {'status': 'empty', 'category': category.slug, 'run_id': run.pk}

        _persist_parsed_batch(category, source, parsed_products, sync=sync, run=run)

        run.status = ParseRun.Status.OK
        run.finished_at = timezone.now()
        run.save(update_fields=[
            'status', 'finished_at', 'parsed_count', 'saved_offers',
            'new_offers', 'new_products', 'saved_prices', 'updated_at',
        ])
        logger.info(
            '%s %s: спарсено %d, офферов %d (новых %d), товаров создано %d, цен сохранено %d за %.1f сек',
            log_label, category.slug, run.parsed_count, run.saved_offers,
            run.new_offers, run.new_products, run.saved_prices,
            time.monotonic() - t0,
        )
        return {
            'status': 'ok',
            'category': category.slug,
            'parsed': run.parsed_count,
            'run_id': run.pk,
        }
    except Exception as exc:
        run.status = ParseRun.Status.ERROR
        run.finished_at = timezone.now()
        run.error_message = f'{type(exc).__name__}: {exc}'[:4000]
        run.save(update_fields=[
            'status', 'finished_at', 'parsed_count', 'error_message',
            'saved_offers', 'new_offers', 'new_products', 'saved_prices', 'updated_at',
        ])
        logger.exception('%s %s: ошибка', log_label, category.slug)
        raise


def parse_category_with_parser(
    category: Category,
    parser: Any,
    *,
    sync: bool = False,
) -> dict:
    dns_slug = category.store_path(PriceHistory.Source.DNS.value)
    if not dns_slug:
        logger.warning(
            'Категория %s: нет активной привязки DNS (CategoryListing)',
            category.slug,
        )
        return {'status': 'skipped', 'category': category.slug, 'reason': 'no_dns_listing'}

    def _do() -> list:
        parsed = parser.parse_category(dns_slug)
        if not parsed and sync:
            logger.info('Повтор категории %s с новым браузером (DNS)…', category.slug)
            parser.close()
            time.sleep(8)
            parsed = parser.parse_category(dns_slug)
        return parsed or []

    return _run_with_instrumentation(
        category=category,
        source=PriceHistory.Source.DNS.value,
        sync=sync,
        parse_fn=_do,
        log_label='Парсинг DNS',
    )


def parse_category_with_parser_citilink(
    category: Category,
    parser: Any,
    *,
    sync: bool = False,
) -> dict:
    path = category.store_path(PriceHistory.Source.CITILINK.value)
    if not path:
        logger.warning(
            'Категория %s: нет активной привязки Ситилинк (CategoryListing)',
            category.slug,
        )
        return {'status': 'skipped', 'category': category.slug, 'reason': 'no_citilink_listing'}

    def _do() -> list:
        parsed = parser.parse_category(path)
        if not parsed and sync:
            logger.info('Повтор категории %s с новым браузером (Citilink)…', category.slug)
            parser.close()
            time.sleep(8)
            parsed = parser.parse_category(path)
        return parsed or []

    return _run_with_instrumentation(
        category=category,
        source=PriceHistory.Source.CITILINK.value,
        sync=sync,
        parse_fn=_do,
        log_label='Парсинг Citilink',
    )


def parse_category_with_parser_ozon(
    category: Category,
    parser: Any,
    *,
    sync: bool = False,
) -> dict:
    url = category.store_path(PriceHistory.Source.OZON.value)
    if not url:
        logger.warning(
            'Категория %s: нет активной привязки Ozon (CategoryListing)',
            category.slug,
        )
        return {'status': 'skipped', 'category': category.slug, 'reason': 'no_ozon_listing'}

    def _do() -> list:
        parsed = parser.parse_category(url)
        if not parsed and sync:
            logger.info('Повтор категории %s с новым браузером (Ozon)…', category.slug)
            parser.close()
            time.sleep(8)
            parsed = parser.parse_category(url)
        return parsed or []

    return _run_with_instrumentation(
        category=category,
        source=PriceHistory.Source.OZON.value,
        sync=sync,
        parse_fn=_do,
        log_label='Парсинг Ozon',
    )


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
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
    acks_late=True,
)
def task_parse_citilink_category(self, category_id: int) -> dict:
    from .citilink_parser import CitilinkParser

    try:
        category = Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist:
        logger.warning('Категория id=%d не найдена или неактивна', category_id)
        return {'status': 'skipped', 'reason': 'category_not_found'}

    with CitilinkParser() as parser:
        return parse_category_with_parser_citilink(category, parser)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
    acks_late=True,
)
def task_parse_ozon_category(self, category_id: int) -> dict:
    from .ozon_parser import OzonParser

    try:
        category = Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist:
        logger.warning('Категория id=%d не найдена или неактивна', category_id)
        return {'status': 'skipped', 'reason': 'category_not_found'}

    with OzonParser() as parser:
        return parse_category_with_parser_ozon(category, parser)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,
    retry_backoff_max=120,
    max_retries=5,
)
def task_save_price(
    self,
    offer_id: int | None = None,
    product_id: int | None = None,
    price: int = 0,
    old_price: int | None = None,
    timestamp: str | None = None,
    source: str | None = None,
) -> dict:
    offer: Offer | None = None
    product: Product | None = None
    if offer_id is not None:
        try:
            offer = Offer.objects.select_related('product').get(pk=offer_id)
        except Offer.DoesNotExist:
            logger.warning('Оффер id=%d не найден', offer_id)
            return {'status': 'skipped', 'reason': 'offer_not_found'}
        product = offer.product

        source = offer.source
    elif product_id is not None:
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.warning('Товар id=%d не найден', product_id)
            return {'status': 'skipped', 'reason': 'product_not_found'}
    else:
        logger.warning('task_save_price вызван без offer_id/product_id')
        return {'status': 'skipped', 'reason': 'no_ids'}

    ts = datetime.fromisoformat(timestamp) if timestamp else timezone.now()

    allowed_sources = {c.value for c in PriceHistory.Source}
    src = (source or PriceHistory.Source.DNS.value).lower()
    if src not in allowed_sources:
        src = PriceHistory.Source.DNS.value


    last_qs = PriceHistory.objects.filter(product=product, source=src, is_actual=True)
    if offer is not None:
        last_qs = last_qs.filter(offer=offer)
    last_record = last_qs.order_by('-timestamp').first()

    price_decimal = Decimal(str(price))
    old_price_decimal = Decimal(str(old_price)) if old_price else None

    if last_record and last_record.price == price_decimal:
        logger.debug('Цена %s (%s) не изменилась (%s₽)', product.name, src, price_decimal)
        return {'status': 'unchanged', 'product_id': product.pk}

    if last_record:
        last_record.is_actual = False
        last_record.save(update_fields=['is_actual', 'updated_at'])

    PriceHistory.objects.create(
        product=product,
        offer=offer,
        price=price_decimal,
        old_price=old_price_decimal,
        timestamp=ts,
        is_actual=True,
        source=src,
    )

    logger.info('Сохранена цена для %s: %s₽', product.name, price_decimal)

    return {
        'status': 'saved',
        'product_id': product.pk,
        'offer_id': offer.pk if offer else None,
        'source': src,
        'price': str(price_decimal),
    }


@shared_task
def task_pause_between_dns_categories(seconds: int) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _cleanup_stuck_parseruns(timeout_minutes: int) -> dict:
    cutoff = timezone.now() - timedelta(minutes=timeout_minutes)
    now = timezone.now()
    stuck_qs = ParseRun.objects.filter(
        status=ParseRun.Status.RUNNING,
        started_at__lt=cutoff,
    )


    updated = stuck_qs.update(
        status=ParseRun.Status.ERROR,
        finished_at=now,
        error_message=(
            f'stuck_timeout: ParseRun висел в RUNNING > {timeout_minutes} мин '
            f'(вероятно, воркер умер OOM/kill-9). Закрыт автоматически.'
        ),
        updated_at=now,
    )
    return {'cleaned': updated, 'timeout_minutes': timeout_minutes, 'cutoff': cutoff.isoformat()}


@shared_task
def task_cleanup_stuck_parseruns(timeout_minutes: int | None = None) -> dict:
    minutes = int(
        timeout_minutes
        if timeout_minutes is not None
        else getattr(settings, 'PARSE_RUN_STUCK_TIMEOUT_MINUTES', 30)
    )
    result = _cleanup_stuck_parseruns(timeout_minutes=minutes)
    if result['cleaned']:
        logger.warning(
            'ParseRun cleanup: помечено как ERROR %d зависших прогонов (>%d мин)',
            result['cleaned'], minutes,
        )
    return result


@shared_task
def task_parse_all_categories() -> dict:
    categories = list(
        Category.objects.filter(
            is_active=True,
            listings__source=CategoryListing.Source.DNS,
            listings__is_active=True,
        )
        .exclude(listings__external_path='')
        .distinct()
        .order_by('id')
    )
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
