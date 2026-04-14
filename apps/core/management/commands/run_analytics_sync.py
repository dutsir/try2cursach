from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.analytics.detector import run_full_detection
from apps.products.models import Product


class Command(BaseCommand):
    help = 'Запускает только аналитику (детекцию аномалий) синхронно, без Celery.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--product-id', type=int, help='Запустить аналитику только для одного товара')
        parser.add_argument('--category', type=str, help='Slug категории: анализ только для товаров категории')
        parser.add_argument('--limit', type=int, help='Ограничить число товаров (для быстрых прогонов)')

    def handle(self, *args: Any, **options: Any) -> None:
        product_id = options.get('product_id')
        category_slug = options.get('category')
        limit = options.get('limit')

        if product_id:
            product_ids = [product_id]
        else:
            qs = Product.objects.filter(is_active=True)
            if category_slug:
                qs = qs.filter(category__slug=category_slug)
            qs = qs.order_by('id').values_list('id', flat=True)
            if limit:
                qs = qs[: max(int(limit), 1)]
            product_ids = list(qs)

        total = len(product_ids)
        if total == 0:
            self.stdout.write(self.style.WARNING('Нет товаров для анализа.'))
            return

        self.stdout.write(self.style.NOTICE(f'Аналитика: к обработке {total} товаров...'))
        anomalies_created = 0
        errors = 0
        for idx, pid in enumerate(product_ids, start=1):
            try:
                anomalies = run_full_detection(pid)
                anomalies_created += len(anomalies)
            except Exception as exc:
                errors += 1
                self.stderr.write(self.style.WARNING(f'  Ошибка для product_id={pid}: {exc}'))
            if idx % 25 == 0 or idx == total:
                self.stdout.write(
                    f'  Обработано {idx}/{total}, новых аномалий: {anomalies_created}, ошибок: {errors}'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Готово: товаров {total}, новых аномалий {anomalies_created}, ошибок {errors}.'
            )
        )
