from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.products.models import Category, Product


class Command(BaseCommand):
    help = 'Показывает несколько примеров названий товаров в категории.'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument('slug')
        parser.add_argument('--limit', type=int, default=15)
        parser.add_argument('--exclude', default='',
                            help='Подстрока в name, которую исключить (например, "баллов")')

    def handle(self, *args: Any, **opts: Any) -> None:
        cat = Category.objects.filter(slug=opts['slug']).first()
        if cat is None:
            self.stderr.write(f'Категория не найдена: {opts["slug"]}')
            return
        qs = Product.objects.filter(category=cat)
        if opts['exclude']:
            qs = qs.exclude(name__icontains=opts['exclude'])
        qs = qs.only(
            'id', 'name', 'brand', 'vendor_code', 'specs_fingerprint',
        )[:opts['limit']]
        for p in qs:
            specs = dict(p.specs_fingerprint or {})
            self.stdout.write(
                f'id={p.id} brand={p.brand!r} mpn={p.vendor_code!r} specs={specs}'
            )
            self.stdout.write(f'  {p.name}')
            self.stdout.write('')
