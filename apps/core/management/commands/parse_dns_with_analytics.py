from __future__ import annotations

import argparse
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from apps.prices.models import PriceHistory


class Command(BaseCommand):
    help = (
        'Синхронный парсинг DNS; опционально — курсы ЦБ, аномалии, ARIMA (без Celery). '
        'По умолчанию только парсинг: детекция аномалий выключена (режим агрегатора цен). '
        'Включить аномалии: ENABLE_ADVANCED_ANALYTICS=1 или флаг --anomalies. '
        'ARIMA: ENABLE_ADVANCED_ANALYTICS=1 и --forecast. '
        'При включённой аналитике в Celery аномалии также ставятся после сохранения цены.'
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
        parser.add_argument(
            '--anomalies',
            action='store_true',
            help='После парсинга запустить детекцию аномалий по товарам с новыми ценами '
            '(даже если ENABLE_ADVANCED_ANALYTICS выключен).',
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
            self.stdout.write(self.style.WARNING('Новых записей цен нет, шаги после парсинга пропущены.'))
            return

        run_anomalies = bool(getattr(settings, 'ENABLE_ADVANCED_ANALYTICS', False) or options.get('anomalies'))
        if run_anomalies:
            from apps.analytics.detector import run_full_detection

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
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f'Детекция аномалий пропущена ({total} товаров с новыми ценами). '
                    'Включить: ENABLE_ADVANCED_ANALYTICS=1 или запуск с --anomalies.'
                )
            )

        if options.get('forecast'):
            if not getattr(settings, 'ENABLE_ADVANCED_ANALYTICS', False):
                self.stderr.write(
                    self.style.WARNING(
                        'ARIMA-прогноз пропущен: задайте ENABLE_ADVANCED_ANALYTICS=1 в окружении.'
                    )
                )
            else:
                self.stdout.write(self.style.NOTICE('Шаг: ARIMA-прогноз для затронутых товаров...'))
                from apps.analytics.forecasting import forecast_for_product_ids

                horizon = max(int(options.get('forecast_horizon') or 7), 1)
                result = forecast_for_product_ids(product_ids, horizon=horizon)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Прогноз: создано точек {result["forecasts_created"]}, ошибок {result["errors"]}.'
                    )
                )
