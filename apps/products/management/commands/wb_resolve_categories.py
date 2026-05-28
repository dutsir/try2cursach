"""Резолв WB категорий: качает main-menu, создаёт CategoryListing.

Маппит slug наших категорий на русские имена в WB-каталоге,
вытаскивает shard+query и создаёт CategoryListing(source='wb').

Использование:
    python manage.py wb_resolve_categories --dry-run    # показать что нашли
    python manage.py wb_resolve_categories --apply       # создать/обновить листинги
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.prices.wildberries_parser import (
    download_wb_catalog_tree,
    find_category_in_tree,
)
from apps.products.models import Category, CategoryListing

logger = logging.getLogger(__name__)


# Маппинг slug наших категорий → русское имя в WB каталоге.
# Auto-resolver сначала пробует найти по slug в URL, потом по этому имени.
# Подбирается опытным путём при первом запуске.
WB_CATEGORY_NAME_MAP = {
    # === 8 категорий комплектующих (выбор пользователя) ===
    'processory': 'Процессоры',
    'videokarty': 'Видеокарты',
    'materinskie-platy': 'Материнские платы',
    'operativnaya-pamyat': 'Оперативная память',
    'ssd-nakopiteli': 'Твердотельные накопители SSD',
    'zhestkie-diski-35': 'Жесткие диски',
    'bloki-pitaniya': 'Блоки питания',
    'korpusa': 'Корпуса',
    # === Периферия и ноутбуки ===
    'noutbuki': 'Ноутбуки',
    'klaviatury': 'Клавиатуры',
    'myshi': 'Мыши',
}


class Command(BaseCommand):
    help = 'Резолвит WB-категории из main-menu и создаёт CategoryListing(source=wb)'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Только показать что найдено, не сохранять.',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='Создать/обновить CategoryListing в БД.',
        )
        parser.add_argument(
            '--force-refresh', action='store_true',
            help='Заново скачать дерево WB (игнорировать Redis кэш).',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = options.get('dry_run', False)
        apply = options.get('apply', False)
        force = options.get('force_refresh', False)

        if not dry_run and not apply:
            self.stderr.write(self.style.ERROR(
                'Укажи --dry-run или --apply'
            ))
            return

        self.stdout.write('Скачиваю дерево категорий WB...')
        tree = download_wb_catalog_tree(force_refresh=force)
        self.stdout.write(f'  ✓ {len(tree)} записей в дереве')

        # Резолвим каждый slug
        resolved: list[dict] = []
        not_found: list[str] = []
        for slug, ru_name in WB_CATEGORY_NAME_MAP.items():
            entry = find_category_in_tree(slug, tree)
            if not entry:
                entry = find_category_in_tree(ru_name, tree)
            if entry and entry.get('shard') and entry.get('query'):
                resolved.append({
                    'slug': slug,
                    'ru_name': ru_name,
                    'wb_name': entry['name'],
                    'shard': entry['shard'],
                    'query': entry['query'],
                    'wb_url': entry['url'],
                })
            else:
                not_found.append(slug)

        # Печатаем результат
        self.stdout.write('\n=== Резолв ===')
        for r in resolved:
            external_path = f'shard:{r["shard"]}|query:{r["query"]}'
            self.stdout.write(
                f'  ✓ {r["slug"]:30} → {r["wb_name"]:35} '
                f'shard={r["shard"]} query={r["query"][:50]}'
            )

        if not_found:
            self.stdout.write(self.style.WARNING(
                '\nНе найдены:'
            ))
            for s in not_found:
                ru = WB_CATEGORY_NAME_MAP.get(s, '?')
                self.stdout.write(f'  ✗ {s} ({ru})')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\n(dry-run: ничего не сохранено)'
            ))
            return

        # Применяем — создаём/обновляем CategoryListing
        created = 0
        updated = 0
        skipped = 0
        for r in resolved:
            try:
                category = Category.objects.get(slug=r['slug'])
            except Category.DoesNotExist:
                self.stderr.write(self.style.WARNING(
                    f'  ⚠ Категория {r["slug"]} не найдена в БД, пропускаю'
                ))
                skipped += 1
                continue

            external_path = f'shard:{r["shard"]}|query:{r["query"]}'
            listing, was_created = CategoryListing.objects.update_or_create(
                category=category,
                source=CategoryListing.Source.WB,
                defaults={
                    'external_path': external_path,
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  + создан listing: {r["slug"]:30} → {external_path}'
                ))
            else:
                updated += 1
                self.stdout.write(
                    f'  ~ обновлён listing: {r["slug"]:30} → {external_path}'
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: создано {created}, обновлено {updated}, пропущено {skipped}, '
            f'не найдено {len(not_found)}'
        ))
