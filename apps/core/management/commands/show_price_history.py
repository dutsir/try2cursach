from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.prices.models import PriceHistory
from apps.products.models import Product


class Command(BaseCommand):
    help = 'Показывает историю изменения цены по товару в табличном виде.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--product-id', type=int, help='ID товара')
        parser.add_argument('--slug', type=str, help='Slug товара')
        parser.add_argument('--name', type=str, help='Часть названия товара')
        parser.add_argument('--limit', type=int, default=30, help='Сколько последних записей показать')

    def handle(self, *args: Any, **options: Any) -> None:
        provided = [bool(options.get('product_id')), bool(options.get('slug')), bool(options.get('name'))]
        if sum(provided) != 1:
            raise CommandError('Укажите ровно один фильтр: --product-id или --slug или --name')

        product = self._resolve_product(options)
        limit = max(int(options.get('limit') or 30), 1)

        rows = list(
            PriceHistory.objects
            .filter(product=product)
            .order_by('-timestamp')[:limit]
        )
        if not rows:
            self.stdout.write(self.style.WARNING('Для товара пока нет истории цен.'))
            return

        rows.reverse()  # Показываем в хронологическом порядке: старые -> новые

        self.stdout.write(f'Товар: {product.name}')
        self.stdout.write(f'URL: {product.url}')
        self.stdout.write(f'Записей: {len(rows)} (лимит {limit})')
        self.stdout.write('')
        self.stdout.write('Дата и время           | Цена     | Старая   | Изменение к пред. | %')
        self.stdout.write('-' * 78)

        prev_price: Decimal | None = None
        for rec in rows:
            curr = rec.price
            old = rec.old_price
            if prev_price is None:
                delta_str = '-'
                pct_str = '-'
            else:
                delta = curr - prev_price
                sign = '+' if delta > 0 else ''
                delta_str = f'{sign}{delta:.2f}'
                if prev_price == 0:
                    pct_str = '-'
                else:
                    pct = (delta / prev_price) * Decimal('100')
                    pct_sign = '+' if pct > 0 else ''
                    pct_str = f'{pct_sign}{pct:.2f}%'

            ts = rec.timestamp.strftime('%Y-%m-%d %H:%M')
            old_str = f'{old:.2f}' if old is not None else '-'
            self.stdout.write(
                f'{ts:20} | {curr:8.2f} | {old_str:8} | {delta_str:16} | {pct_str}'
            )
            prev_price = curr

    def _resolve_product(self, options: dict[str, Any]) -> Product:
        if options.get('product_id'):
            try:
                return Product.objects.get(pk=options['product_id'])
            except Product.DoesNotExist as exc:
                raise CommandError(f"Товар с id={options['product_id']} не найден") from exc

        if options.get('slug'):
            try:
                return Product.objects.get(slug=options['slug'])
            except Product.DoesNotExist as exc:
                raise CommandError(f"Товар со slug='{options['slug']}' не найден") from exc

        query = str(options['name']).strip()
        qs = Product.objects.filter(name__icontains=query).order_by('id')[:5]
        matches = list(qs)
        if not matches:
            raise CommandError(f"Товары по запросу '{query}' не найдены")
        if len(matches) > 1:
            lines = '\n'.join([f'  id={p.id} slug={p.slug} name={p.name}' for p in matches])
            raise CommandError(
                'Найдено несколько товаров. Уточните через --product-id или --slug.\n'
                f'{lines}'
            )
        return matches[0]
