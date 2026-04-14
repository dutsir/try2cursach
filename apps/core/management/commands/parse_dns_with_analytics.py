from __future__ import annotations

import argparse
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from apps.analytics.detector import run_full_detection
from apps.prices.models import PriceHistory


class Command(BaseCommand):
    help = (
        'Синхронный парсинг DNS + аналитика без Celery. '
        'По умолчанию: парсинг + детекция аномалий по товарам с новыми ценами. '
        'Опции --cbr и --forecast добавляют шаги (см. help). '
        'В Celery аномалии уже запускаются после каждого сохранения цены (task_save_price).'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--sync',
            action=argparse.BooleanOptionalAction,
            default=True,
            help='Как у parse_dns: сохранять цены синхронно без Celery (по умолчанию: да). '
            'С --no-sync цены уходят в очередь — шаг аналитики может не увидеть все обновления.',
        )
        parser.add_argument('--category', type=str)
        parser.add_argument('--reuse-browser', action='store_true')
        h = parser.add_mutually_exclusive_group()
        h.add_argument('--headless', action='store_true')
        h.add_argument('--no-headless', action='store_true')
        parser.add_argument(
            '--cbr',
            action='store_true',
            help='Перед парсингом загрузить курсы ЦБ РФ за сегодня (для корреляций / отчётов).',
        )
        parser.add_argument(
            '--forecast',
            action='store_true',
            help='После аномалий построить ARIMA-прогноз только для товаров с новыми ценами в этом запуске.',
        )
        parser.add_argument(
            '--forecast-horizon',
            type=int,
            default=7,
            help='Горизонт прогноза в днях (с --forecast).',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        started_at = timezone.now()

        if options.get('cbr'):
            self.stdout.write(self.style.NOTICE('Шаг: курсы ЦБ РФ за сегодня...'))
            from apps.analytics.cbr_rates import save_rates_for_date

            try:
                save_rates_for_date()
                self.stdout.write(self.style.SUCCESS('  Курсы ЦБ обновлены.'))
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f'  ЦБ: не удалось загрузить ({exc})'))

        use_sync = bool(options.get('sync', True))
        if not use_sync:
            self.stderr.write(self.style.WARNING(
                'Режим --no-sync: аналитика сразу после парсинга может не включить все товары '
                '(цены ещё сохраняются воркером). Для полного совпадения используйте --sync.'
            ))

        cmd_options: dict[str, Any] = {'sync': use_sync}
        if options.get('category'):
            cmd_options['category'] = options['category']
        if options.get('reuse_browser'):
            cmd_options['reuse_browser'] = True
        if options.get('headless'):
            cmd_options['headless'] = True
        if options.get('no_headless'):
            cmd_options['no_headless'] = True

        self.stdout.write(self.style.NOTICE(f'Шаг: парсинг DNS (sync={use_sync})...'))
        call_command('parse_dns', **cmd_options)

        product_ids = list(
            PriceHistory.objects
            .filter(timestamp__gte=started_at)
            .values_list('product_id', flat=True)
            .distinct()
        )
        total = len(product_ids)
        if total == 0:
            self.stdout.write(self.style.WARNING('Новых записей цен нет, аналитика не запущена.'))
            return

        self.stdout.write(self.style.NOTICE(f'Шаг: детекция аномалий ({total} товаров)...'))
        anomalies_created = 0
        for idx, product_id in enumerate(product_ids, start=1):
            anomalies = run_full_detection(product_id)
            anomalies_created += len(anomalies)
            if idx % 25 == 0 or idx == total:
                self.stdout.write(f'  Обработано {idx}/{total}, новых аномалий: {anomalies_created}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Аномалии: проанализировано {total} товаров, новых аномалий: {anomalies_created}.'
            )
        )

        if options.get('forecast'):
            self.stdout.write(self.style.NOTICE('Шаг: ARIMA-прогноз для затронутых товаров...'))
            from apps.analytics.forecasting import forecast_for_product_ids

            horizon = max(int(options.get('forecast_horizon') or 7), 1)
            result = forecast_for_product_ids(product_ids, horizon=horizon)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Прогноз: создано точек {result["forecasts_created"]}, ошибок {result["errors"]}.'
                )
            )
