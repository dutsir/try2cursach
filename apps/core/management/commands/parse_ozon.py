import random
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from apps.products.models import Category, CategoryListing
from apps.prices.ozon_parser import OzonParser
from apps.prices.tasks import parse_category_with_parser_ozon, task_parse_ozon_category


class Command(BaseCommand):
    help = 'Парсинг Ozon для категорий с активной привязкой CategoryListing (источник «Ozon»)'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--category', type=str, help='Slug категории в БД')
        parser.add_argument('--sync', action='store_true')
        h = parser.add_mutually_exclusive_group()
        h.add_argument(
            '--headless',
            action='store_true',
            help='Без окна Chrome (перекрывает CHROME_HEADLESS из .env на время команды)',
        )
        h.add_argument('--no-headless', action='store_true', help='Всегда показывать окно браузера')
        rb = parser.add_mutually_exclusive_group()
        rb.add_argument(
            '--reuse-browser',
            dest='reuse_browser',
            action='store_true',
            default=True,
            help='С --sync: один Chrome на все категории (по умолчанию). '
                 'Так сохраняется warmup/cookies между категориями.',
        )
        rb.add_argument(
            '--no-reuse-browser',
            dest='reuse_browser',
            action='store_false',
            help='Пересоздавать Chrome на каждую категорию. Не рекомендуется: '
                 'warmup/куки Ozon теряются, возрастает шанс капчи.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        category_slug: str | None = options.get('category')
        is_sync: bool = options.get('sync', False)
        prev_headless: bool = bool(getattr(settings, 'CHROME_HEADLESS', True))
        if options.get('headless'):
            settings.CHROME_HEADLESS = True
        elif options.get('no_headless'):
            settings.CHROME_HEADLESS = False

        qs = (
            Category.objects.filter(is_active=True)
            .filter(
                listings__source=CategoryListing.Source.OZON,
                listings__is_active=True,
            )
            .exclude(listings__external_path='')
            .distinct()
        )
        if category_slug:
            qs = qs.filter(slug=category_slug)

        if not qs.exists():
            self.stderr.write(
                self.style.ERROR(
                    'Нет категорий с активной привязкой Ozon. '
                    'В админке у категории добавьте каталог магазина «Ozon» (URL раздела).'
                )
            )
            settings.CHROME_HEADLESS = prev_headless
            return

        try:
            cat_list = list(qs.order_by('id'))
            cd_min = float(getattr(settings, 'DNS_SYNC_CATEGORY_COOLDOWN_MIN', 45))
            cd_max = float(getattr(settings, 'DNS_SYNC_CATEGORY_COOLDOWN_MAX', 120))
            reuse_browser = bool(options.get('reuse_browser'))

            if is_sync and cat_list:
                self.stdout.write(
                    self.style.NOTICE(
                        f'Ozon, синхронно: {len(cat_list)} категорий, '
                        f'пауза {cd_min:.0f}–{cd_max:.0f}с, '
                        f"браузер: {'один' if reuse_browser else 'новый на категорию'}."
                    )
                )

                def run_one(category: Category, parser: OzonParser) -> None:
                    self.stdout.write(f'Ozon: {category.name} ({category.slug})')
                    result = parse_category_with_parser_ozon(category, parser, sync=True)
                    st = result.get('status')
                    if st == 'skipped':
                        self.stderr.write(self.style.WARNING(f'  {category.slug}: пропуск ({result}).'))
                    elif st == 'empty':
                        self.stderr.write(self.style.WARNING(f'  {category.slug}: 0 товаров.'))
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  {category.slug}: {result.get("parsed", 0)} товаров.'
                            )
                        )

                if reuse_browser:
                    with OzonParser() as parser:
                        for i, category in enumerate(cat_list):
                            if i > 0:
                                delay = random.uniform(cd_min, cd_max)
                                self.stdout.write(f'  Пауза {delay:.0f}с…')
                                time.sleep(delay)
                            run_one(category, parser)
                else:
                    for i, category in enumerate(cat_list):
                        if i > 0:
                            delay = random.uniform(cd_min, cd_max)
                            self.stdout.write(f'  Пауза {delay:.0f}с…')
                            time.sleep(delay)
                        with OzonParser() as parser:
                            run_one(category, parser)
            else:
                for category in cat_list:
                    self.stdout.write(f'Ozon: постановка в очередь {category.name} ({category.slug})')
                    task_parse_ozon_category.delay(category.id)
                    self.stdout.write(self.style.SUCCESS('  Задача поставлена'))
        finally:
            settings.CHROME_HEADLESS = prev_headless

        self.stdout.write(self.style.SUCCESS('Готово'))
