from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.products.models import Category


BUILTIN_CATEGORIES: list[dict[str, str]] = [
    {
        'name': 'Оперативная память',
        'slug': 'operativnaya-pamyat',
        'dns_category_slug': '17a89a3916404e77/operativnaya-pamyat',
    },
    {
        'name': 'Мониторы',
        'slug': 'monitory',
        'dns_category_slug': '17a8943d16404e77/monitory',
    },
    {
        'name': 'Видеокарты',
        'slug': 'videokarty',
        'dns_category_slug': '17a89aab16404e77/videokarty',
    },
    {
        'name': 'Блоки питания',
        'slug': 'bloki-pitaniya',
        'dns_category_slug': '17a89c2216404e77/bloki-pitaniya',
    },
    {
        'name': 'Процессоры',
        'slug': 'processory',
        'dns_category_slug': '17a899cd16404e77/processory',
    },
    {
        'name': 'Материнские платы',
        'slug': 'materinskie-platy',
        'dns_category_slug': '17a89a0416404e77/materinskie-platy',
    },
    {
        'name': 'SSD-накопители',
        'slug': 'ssd-nakopiteli',
        'dns_category_slug': '8a9ddfba20724e77/ssd-nakopiteli',
    },
    {
        'name': 'Жёсткие диски 3.5" (HDD)',
        'slug': 'zhestkie-diski-35',
        'dns_category_slug': '17a8914916404e77/zestkie-diski-3.5',
    },
    {
        'name': 'Корпуса',
        'slug': 'korpusa',
        'dns_category_slug': '17a89c5616404e77/korpusa',
    },
    {
        'name': 'Оптические приводы',
        'slug': 'opticheskie-privody',
        'dns_category_slug': '17a9c97816404e77/opticeskie-privody',
    },
    {
        'name': 'Звуковые карты',
        'slug': 'zvukovye-karty',
        'dns_category_slug': '17a89b4f16404e77/zvukovye-karty',
    },
    {
        'name': 'Карты видеозахвата',
        'slug': 'karty-videozahvata',
        'dns_category_slug': '17a89b8416404e77/karty-videozahvata',
    },
    {
        'name': 'Внешние оптические приводы',
        'slug': 'vneshnie-opticheskie-privody',
        'dns_category_slug': 'recipe/a93cd0f2071b812a/vnesnie-opticeskie-privody',
    },
    {
        'name': 'Платы расширения',
        'slug': 'platy-rasshireniya',
        'dns_category_slug': '17a89bb916404e77/platy-rassirenia',
    },
    {
        'name': 'Адаптеры для накопителей',
        'slug': 'adaptery-dlya-nakopitelej',
        'dns_category_slug': 'ed60465eacbf3c59/adaptery-dla-nakopitelej',
    },
    {
        'name': 'Многофункциональные панели',
        'slug': 'mnogofunkcionalnye-paneli',
        'dns_category_slug': 'ebc01709b094a079/mnogofunkcionalnye-paneli',
    },
    {
        'name': 'Аксессуары для материнских плат',
        'slug': 'aksessuary-dlya-materinskih-plat',
        'dns_category_slug': '2c0f47131ade2231/aksessuary-dla-materinskih-plat',
    },
    {
        'name': 'Сетевые карты',
        'slug': 'setevye-karty',
        'dns_category_slug': '17a8a9e816404e77/setevye-karty',
    },
    {
        'name': 'Серверные процессоры',
        'slug': 'servernye-processory',
        'dns_category_slug': '17a9de1b16404e77/servernye-processory',
    },
    {
        'name': 'Серверные материнские платы',
        'slug': 'servernye-materinskie-platy',
        'dns_category_slug': '17aa955316404e77/servernye-materinskie-platy',
    },
    {
        'name': 'Серверные накопители',
        'slug': 'servernye-nakopiteli',
        'dns_category_slug': 'e7b8dd636db510c5/servernye-nakopiteli',
    },
    {
        'name': 'Серверная память',
        'slug': 'servernaya-pamyat',
        'dns_category_slug': 'recipe/4665d1c30d258853/servernaa-pamat',
    },
    {
        'name': 'Серверные блоки питания',
        'slug': 'servernye-bloki-pitaniya',
        'dns_category_slug': '4be07aa32e7a4e77/servernye-bp',
    },
    {
        'name': 'Серверные корпуса',
        'slug': 'servernye-korpusa',
        'dns_category_slug': '17a9e95b16404e77/servernye-korpusa',
    },
    {
        'name': 'Корзины для накопителей',
        'slug': 'korziny-dlya-nakopitelej',
        'dns_category_slug': 'd1b66c37b97c8cc4/korziny-dla-nakopitelej',
    },
    {
        'name': 'Серверные кабели и переходники',
        'slug': 'servernye-kabeli-i-perehodniki',
        'dns_category_slug': '8f96686c51a99374/servernye-kabeli-i-perehodniki',
    },
    {
        'name': 'Охлаждение для серверных процессоров',
        'slug': 'ohlazhdenie-dlya-servernyh-processorov',
        'dns_category_slug': 'bbbfd86bd37e0b91/ohlazdenie-dla-servernyh-processorov',
    },
    {
        'name': 'Серверные направляющие',
        'slug': 'servernye-napravlyayushchie',
        'dns_category_slug': '6cbd9f23e7066c55/servernye-napravlausie',
    },
    {
        'name': 'Аксессуары для серверных корпусов',
        'slug': 'aksessuary-dlya-servernyh-korpusov',
        'dns_category_slug': 'e6d959c943e32156/aksessuary-dla-servernyh-korpusov',
    },
    {
        'name': 'Серверные операционные системы',
        'slug': 'servernye-operacionnye-sistemy',
        'dns_category_slug': '62c92d5946d337c4/servernye-operacionnye-sistemy',
    },
]


class Command(BaseCommand):
    help = (
        'Создаёт категории для парсера DNS (по уникальному slug). '
        'Встроенные пути соответствуют каталогам dns-shop.ru; если раздел открывается иначе, '
        'исправьте dns_category_slug в админке или в JSON.'
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--file',
            type=str,
            default='',
            metavar='PATH',
            help='JSON: массив объектов {"name","slug","dns_category_slug"}',
        )
        parser.add_argument(
            '--only-file',
            action='store_true',
            help='Только из --file, без встроенного списка',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать действия без записи в БД',
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Обновить name и dns_category_slug, если запись с таким slug уже есть',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        rows = self._load_rows(
            file_path=options['file'],
            only_file=options['only_file'],
        )
        merged: dict[str, dict[str, str]] = {}
        for row in rows:
            merged[row['slug'].strip()] = row
        rows = list(merged.values())

        dry = options['dry_run']
        do_update = options['update']

        created_n = 0
        updated_n = 0
        skipped_n = 0

        for row in rows:
            slug = row['slug'].strip()
            name = row['name'].strip()
            dns = row['dns_category_slug'].strip().strip('/')
            if not slug or not name or not dns:
                raise CommandError(f'Пустое поле в записи: {row!r}')

            exists = Category.objects.filter(slug=slug).first()
            if exists is None:
                if dry:
                    self.stdout.write(self.style.WARNING(f'+ создать: {slug} ({name})'))
                else:
                    Category.objects.create(
                        name=name,
                        slug=slug,
                        dns_category_slug=dns,
                        is_active=True,
                    )
                created_n += 1
                continue

            if do_update:
                if dry:
                    self.stdout.write(self.style.WARNING(f'~ обновить: {slug}'))
                else:
                    Category.objects.filter(pk=exists.pk).update(
                        name=name,
                        dns_category_slug=dns,
                        is_active=True,
                    )
                updated_n += 1
            else:
                skipped_n += 1
                self.stdout.write(f'— пропуск (уже есть): {slug}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Готово: создано {created_n}, обновлено {updated_n}, пропущено {skipped_n}'
                + (' (dry-run)' if dry else '')
            )
        )

    def _load_rows(self, file_path: str, only_file: bool) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if not only_file:
            rows.extend(BUILTIN_CATEGORIES)

        if not file_path:
            return rows

        path = Path(file_path)
        if not path.is_file():
            raise CommandError(f'Файл не найден: {path}')

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise CommandError(f'Некорректный JSON: {exc}') from exc

        if not isinstance(data, list):
            raise CommandError('JSON должен быть массивом объектов')

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise CommandError(f'Элемент {i} не объект')
            try:
                rows.append(
                    {
                        'name': str(item['name']),
                        'slug': str(item['slug']),
                        'dns_category_slug': str(item['dns_category_slug']),
                    }
                )
            except KeyError as exc:
                raise CommandError(f'В элементе {i} нет ключа {exc}') from exc

        return rows
