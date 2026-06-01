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

    # Обновить extra_metadata для офферов с дополнительными полями (rating, brand и т.п.)
    items_with_extra = [
        item for item in parsed_products
        if getattr(item, 'extra', None)
    ]
    if items_with_extra:
        raw_names = [item.name for item in items_with_extra]
        offers_by_name = {
            o.raw_name: o
            for o in Offer.objects.filter(source=source, raw_name__in=raw_names)
        }
        extra_updated = 0
        for item in items_with_extra:
            offer = offers_by_name.get(item.name)
            if not offer:
                continue
            merged = dict(offer.extra_metadata or {})
            merged.update(item.extra)
            offer.extra_metadata = merged
            offer.save(update_fields=['extra_metadata', 'updated_at'])
            extra_updated += 1
        if extra_updated:
            logger.info(
                'Обновлены extra_metadata для %d офферов (source=%s)',
                extra_updated, source,
            )

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


def parse_category_with_parser_mvideo(
    category: Category,
    parser: Any,
    *,
    sync: bool = False,
) -> dict:
    path = category.store_path(PriceHistory.Source.MVIDEO.value)
    if not path:
        logger.warning(
            'Категория %s: нет активной привязки М.Видео (CategoryListing)',
            category.slug,
        )
        return {'status': 'skipped', 'category': category.slug, 'reason': 'no_mvideo_listing'}

    def _do() -> list:
        parsed = parser.parse_category(path)
        if not parsed and sync:
            logger.info('Повтор категории %s с новым браузером (М.Видео)…', category.slug)
            parser.close()
            time.sleep(8)
            parsed = parser.parse_category(path)
        return parsed or []

    return _run_with_instrumentation(
        category=category,
        source=PriceHistory.Source.MVIDEO.value,
        sync=sync,
        parse_fn=_do,
        log_label='Парсинг М.Видео',
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
    from .parsers import DNSBlockedError, DNSParser

    try:
        category = Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist:
        logger.warning('Категория id=%d не найдена или неактивна', category_id)
        return {'status': 'skipped', 'reason': 'category_not_found'}

    # 403 от Qrator — это бан по IP/сети, а не временный сбой. Авторетрай тут вреден:
    # каждый повтор снова стучится на сайт и продлевает/заново вызывает бан. Поэтому
    # ловим DNSBlockedError и завершаем задачу со статусом 'blocked', НЕ пробрасывая
    # её в autoretry_for=(Exception,).
    try:
        with DNSParser() as parser:
            return parse_category_with_parser(category, parser)
    except DNSBlockedError as exc:
        logger.warning('DNS заблокировал парсинг категории %s (403): %s', category.slug, exc)
        return {'status': 'blocked', 'category': category.slug, 'source': 'dns'}


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
def task_parse_mvideo_category(self, category_id: int) -> dict:
    from .mvideo_parser import MVideoBlockedError, MVideoParser

    try:
        category = Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist:
        logger.warning('Категория id=%d не найдена или неактивна', category_id)
        return {'status': 'skipped', 'reason': 'category_not_found'}

    # WAF М.Видео может вернуть antibot-страницу. Это не временный сбой, который
    # лечится повтором (autoretry лишь снова дёргает WAF), поэтому завершаем
    # задачу со статусом 'blocked', не пробрасывая в autoretry_for=(Exception,).
    try:
        with MVideoParser() as parser:
            return parse_category_with_parser_mvideo(category, parser)
    except MVideoBlockedError as exc:
        logger.warning('М.Видео заблокировал парсинг категории %s (WAF): %s', category.slug, exc)
        return {'status': 'blocked', 'category': category.slug, 'source': 'mvideo'}


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


def parse_wb_category_with_parser(
    category: Category,
    parser: Any,
    *,
    sync: bool = False,
) -> dict:
    """Парсинг категории Wildberries (через HTTP API, без Chrome).

    Использует CategoryListing.external_path формата:
      - catalog:  'shard:electronic73|query:subject=3274'
      - search:   'видеокарта'
    """
    wb_path = category.store_path(PriceHistory.Source.WB.value)
    if not wb_path:
        logger.warning(
            'Категория %s: нет активной привязки Wildberries (CategoryListing)',
            category.slug,
        )
        return {'status': 'skipped', 'category': category.slug, 'reason': 'no_wb_listing'}

    def _do() -> list:
        return parser.parse_category(wb_path) or []

    return _run_with_instrumentation(
        category=category,
        source=PriceHistory.Source.WB.value,
        sync=sync,
        parse_fn=_do,
        log_label='Парсинг WB',
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=300,
    max_retries=3,
    acks_late=True,
)
def task_parse_wb_category(self, category_id: int) -> dict:
    from .wildberries_parser import WildberriesParser

    try:
        category = Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist:
        logger.warning('Категория id=%d не найдена или неактивна', category_id)
        return {'status': 'skipped', 'reason': 'category_not_found'}

    with WildberriesParser() as parser:
        return parse_wb_category_with_parser(category, parser)


def parse_regard_category_with_parser(
    category: Category,
    parser: Any,
    *,
    sync: bool = False,
) -> dict:
    """Парсинг категории Регард (через JSON API)."""
    regard_path = category.store_path(PriceHistory.Source.REGARD.value)
    if not regard_path:
        logger.warning(
            'Категория %s: нет активной привязки Регард (CategoryListing)',
            category.slug,
        )
        return {'status': 'skipped', 'category': category.slug, 'reason': 'no_regard_listing'}

    def _do() -> list:
        return parser.parse_category(regard_path) or []

    return _run_with_instrumentation(
        category=category,
        source=PriceHistory.Source.REGARD.value,
        sync=sync,
        parse_fn=_do,
        log_label='Парсинг Регард',
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=300,
    max_retries=3,
    acks_late=True,
)
def task_parse_regard_category(self, category_id: int) -> dict:
    from .regard_parser import RegardParser

    try:
        category = Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist:
        logger.warning('Категория id=%d не найдена или неактивна', category_id)
        return {'status': 'skipped', 'reason': 'category_not_found'}

    with RegardParser() as parser:
        return parse_regard_category_with_parser(category, parser)


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
        # offer.source — авторитетный источник. Если он не входит в PriceHistory.Source,
        # это рассинхрон enum/воркеров (как было с mvideo), а не данные DNS. Не маскируем
        # под 'dns' — это испортило бы историю цен DNS, а громко падаем и пропускаем запись.
        logger.error(
            'task_save_price: источник %r отсутствует в PriceHistory.Source (offer_id=%s, product_id=%s). '
            'Запись пропущена во избежание загрязнения истории DNS — проверьте рассинхрон enum/воркеров.',
            src, offer_id, product_id,
        )
        return {'status': 'skipped', 'reason': 'unknown_source', 'source': src}


    last_qs = PriceHistory.objects.filter(product=product, source=src, is_actual=True)
    if offer is not None:
        last_qs = last_qs.filter(offer=offer)
    last_record = last_qs.order_by('-timestamp').first()

    price_decimal = Decimal(str(price))
    old_price_decimal = Decimal(str(old_price)) if old_price else None

    if last_record and last_record.price == price_decimal:
        logger.debug('Цена %s (%s) не изменилась (%s₽)', product.name, src, price_decimal)
        if offer is not None and offer.current_price != price_decimal:
            # Ленивый бэкилл денормализованной цены для офферов, у которых она ещё пуста.
            offer.current_price = price_decimal
            offer.current_old_price = old_price_decimal
            offer.price_updated_at = last_record.timestamp
            offer.save(update_fields=['current_price', 'current_old_price', 'price_updated_at', 'updated_at'])
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

    if offer is not None:
        offer.current_price = price_decimal
        offer.current_old_price = old_price_decimal
        offer.price_updated_at = ts
        offer.save(update_fields=['current_price', 'current_old_price', 'price_updated_at', 'updated_at'])

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
