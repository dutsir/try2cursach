import logging
import random
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from apps.products.models import Category
from apps.prices.parsers import DNSParser
from apps.prices.tasks import parse_category_with_parser, task_parse_category

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запускает парсинг DNS для указанной категории или всех активных категорий'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--category',
            type=str,
        )
        parser.add_argument(
            '--sync',
            action='store_true',
        )
        h = parser.add_mutually_exclusive_group()
        h.add_argument(
            '--headless',
            action='store_true',
            help='Без окна Chrome (только на время этой команды; перекрывает CHROME_HEADLESS из .env)',
        )
        h.add_argument(
            '--no-headless',
            action='store_true',
            help='Всегда показывать окно браузера',
        )
        parser.add_argument(
            '--reuse-browser',
            action='store_true',
            help='С --sync: один Chrome на все категории',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        category_slug: str | None = options.get('category')
        is_sync: bool = options.get('sync', False)
        prev_headless: bool = bool(getattr(settings, 'CHROME_HEADLESS', True))
        if options.get('headless'):
            settings.CHROME_HEADLESS = True
        elif options.get('no_headless'):
            settings.CHROME_HEADLESS = False

        if category_slug:
            categories = Category.objects.filter(slug=category_slug, is_active=True)
        else:
            categories = Category.objects.filter(is_active=True)

        if not categories.exists():
            self.stderr.write(self.style.ERROR('Активные категории не найдены'))
            settings.CHROME_HEADLESS = prev_headless
            return

        try:
            cat_list = list(categories.order_by('id'))
            cd_min = float(getattr(settings, 'DNS_SYNC_CATEGORY_COOLDOWN_MIN', 45))
            cd_max = float(getattr(settings, 'DNS_SYNC_CATEGORY_COOLDOWN_MAX', 120))
            reuse_browser = bool(options.get('reuse_browser'))
            if is_sync and cat_list:
                self.stdout.write(
                    self.style.NOTICE(
                        f'Синхронный режим: {len(cat_list)} категорий, '
                        f'пауза {cd_min:.0f}–{cd_max:.0f}с, '
                        f"браузер: {'один' if reuse_browser else 'новый на категорию'}."
                    )
                )

                def run_one(category: Category, parser: DNSParser) -> None:
                    self.stdout.write(f'Запуск парсинга: {category.name} ({category.slug})')
                    result = parse_category_with_parser(category, parser, sync=True)
                    if result.get('status') == 'empty':
                        self.stderr.write(
                            self.style.WARNING(
                                f'  {category.slug}: 0 товаров, пропуск.'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  {category.slug}: {result.get("parsed", 0)} товаров.'
                            )
                        )

                if reuse_browser:
                    with DNSParser() as parser:
                        for i, category in enumerate(cat_list):
                            if i > 0:
                                delay = random.uniform(cd_min, cd_max)
                                self.stdout.write(
                                    f'  Пауза {delay:.0f}с перед следующей категорией…'
                                )
                                time.sleep(delay)
                            run_one(category, parser)
                else:
                    for i, category in enumerate(cat_list):
                        if i > 0:
                            delay = random.uniform(cd_min, cd_max)
                            self.stdout.write(
                                f'  Пауза {delay:.0f}с перед следующей категорией…'
                            )
                            time.sleep(delay)
                        with DNSParser() as parser:
                            run_one(category, parser)
            else:
                for category in cat_list:
                    self.stdout.write(f'Запуск парсинга: {category.name} ({category.slug})')
                    task_parse_category.delay(category.id)
                    self.stdout.write(self.style.SUCCESS('Задача поставлена в очередь'))
        finally:
            settings.CHROME_HEADLESS = prev_headless

        self.stdout.write(self.style.SUCCESS('Готово'))
