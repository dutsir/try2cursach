"""Management команда для парсинга Wildberries.

Использует apps.prices.wildberries_parser.WildberriesParser
(HTTP API, без Chrome/Selenium).

Примеры:
    # Парсинг одной категории синхронно
    python manage.py parse_wildberries --category videokarty --sync

    # Парсинг всех активных категорий синхронно
    python manage.py parse_wildberries --sync

    # Парсинг через Celery (асинхронно, нужен worker)
    python manage.py parse_wildberries --category videokarty

    # Dry-run: парсит но не сохраняет в БД (для отладки)
    python manage.py parse_wildberries --category videokarty --sync --dry-run
"""
from __future__ import annotations

import logging
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.prices.wildberries_parser import WildberriesParser
from apps.products.models import Category, CategoryListing

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Парсинг Wildberries для категорий с активной привязкой '
        'в CategoryListing (источник «Wildberries»). '
        'Использует HTTP API, не требует Chrome.'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--category',
            type=str,
            help='Slug категории в нашей БД (например, videokarty)',
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Синхронный парсинг (без Celery). Логи прямо в консоль.',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Парсить все категории с активной привязкой WB.',
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            help='Переопределить WB_MAX_PAGES для одной команды.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Парсить но НЕ сохранять в БД. Для отладки.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        category_slug: str | None = options.get('category')
        is_sync: bool = options.get('sync', False)
        is_dry_run: bool = options.get('dry_run', False)
        max_pages_override: int | None = options.get('max_pages')

        # Найти категории для парсинга
        if category_slug:
            categories = Category.objects.filter(slug=category_slug, is_active=True)
        else:
            categories = Category.objects.filter(is_active=True)

        categories = (
            categories.filter(
                listings__source=CategoryListing.Source.WB,
                listings__is_active=True,
            )
            .exclude(listings__external_path='')
            .distinct()
        )

        if not categories.exists():
            self.stderr.write(
                self.style.ERROR(
                    'Нет категорий с активной привязкой Wildberries. '
                    'В админке у категории добавьте CategoryListing с source=wb '
                    'и external_path (например, "videokarty:8146").'
                )
            )
            return

        cat_list = list(categories.order_by('id'))
        self.stdout.write(
            self.style.NOTICE(
                f'Wildberries, режим {"sync" if is_sync else "async (Celery)"}'
                f'{" + DRY-RUN" if is_dry_run else ""}: '
                f'{len(cat_list)} категорий'
            )
        )

        if not is_sync:
            from apps.prices.tasks import task_parse_wb_category
            for category in cat_list:
                r = task_parse_wb_category.delay(category.id)
                self.stdout.write(
                    f'  {category.slug:30} → task {r.id}'
                )
            self.stdout.write(self.style.SUCCESS(
                f'Поставлено в очередь {len(cat_list)} задач. '
                'Запусти worker: ./scripts/run_celery_worker.sh'
            ))
            return

        # Синхронный парсинг
        with WildberriesParser() as parser:
            if max_pages_override:
                parser.max_pages = max_pages_override
                self.stdout.write(f'  Переопределено max_pages={max_pages_override}')

            for category in cat_list:
                self._parse_one(parser, category, dry_run=is_dry_run)

        self.stdout.write(self.style.SUCCESS('Готово'))

    def _parse_one(
        self,
        parser: WildberriesParser,
        category: Category,
        *,
        dry_run: bool,
    ) -> None:
        """Парсит одну категорию (синхронно)."""
        # Найти CategoryListing для WB
        listing = (
            CategoryListing.objects
            .filter(category=category, source=CategoryListing.Source.WB, is_active=True)
            .first()
        )
        if not listing or not listing.external_path:
            self.stderr.write(
                self.style.WARNING(
                    f'  {category.slug}: пропуск (нет CategoryListing для WB)'
                )
            )
            return

        self.stdout.write(f'Wildberries: {category.name} ({listing.external_path})')
        t0 = time.monotonic()
        try:
            products = parser.parse_category(listing.external_path)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'  {category.slug}: ошибка — {exc}'))
            logger.exception('WB парсинг %s упал', category.slug)
            return

        elapsed = time.monotonic() - t0
        self.stdout.write(
            f'  {category.slug}: {len(products)} товаров за {elapsed:.1f} сек'
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('  (dry-run: НЕ сохраняем в БД)'))
            for p in products[:3]:
                self.stdout.write(
                    f'    └─ {p.name[:80]} → {p.price}₽  extra={p.extra}'
                )
            return

        # Сохранение в БД через общую функцию tasks.py (батчинг + дедупликация + цены)
        from apps.prices.tasks import _persist_parsed_batch
        from apps.prices.models import ParseRun, PriceHistory
        from django.utils import timezone

        # Создаём ParseRun чтобы попало в админку и мониторинг
        run = ParseRun.objects.create(
            source=PriceHistory.Source.WB.value,
            category=category,
            status=ParseRun.Status.RUNNING,
        )
        run.parsed_count = len(products)
        try:
            metrics = _persist_parsed_batch(
                category=category,
                source=PriceHistory.Source.WB.value,
                parsed_products=products,
                sync=True,
                run=run,
            )
            run.status = ParseRun.Status.OK
            run.finished_at = timezone.now()
            run.save(update_fields=[
                'status', 'finished_at', 'parsed_count', 'saved_offers',
                'new_offers', 'new_products', 'saved_prices', 'updated_at',
            ])
            self.stdout.write(
                f'  ✓ saved={metrics["saved"]} new_offers={metrics["new_offers"]} '
                f'new_products={metrics["new_products"]} prices={metrics["saved_prices"]}'
            )
        except Exception as exc:
            run.status = ParseRun.Status.ERROR
            run.error_message = f'{type(exc).__name__}: {exc}'[:4000]
            run.finished_at = timezone.now()
            run.save(update_fields=[
                'status', 'finished_at', 'parsed_count', 'error_message', 'updated_at',
            ])
            self.stderr.write(self.style.ERROR(f'  Сохранение упало: {exc}'))
            logger.exception('WB save %s', category.slug)
