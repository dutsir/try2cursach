"""Единая management-команда для аналитики.

Субкоманды:
  anomalies   — отчёт по аномалиям (текст / JSON)
  clusters    — кластеризация товаров по динамике цен
  index       — индекс цен по категориям
  heatmap     — тепловая карта ценовых изменений
  forecast    — прогноз цен (ARIMA)
  sensitivity — анализ чувствительности к курсу валюты
  metrics     — метрики эффективности парсинга
  deals       — самые выгодные товары
  compare     — сравнение товаров
  cbr         — загрузка курсов ЦБ РФ
  save-snapshot — сохранить снимок аналитики в БД (таблица AnalyticsSnapshot)
  list-snapshots — последние снимки из БД
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = (
        'Аналитические отчёты: anomalies | clusters | index | heatmap | '
        'forecast | sensitivity | metrics | deals | compare | cbr | '
        'save-snapshot | list-snapshots'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        sub = parser.add_subparsers(dest='report', help='Тип отчёта')

        # --- anomalies ---
        p_a = sub.add_parser('anomalies', help='Отчёт по аномалиям')
        p_a.add_argument('--days', type=int, default=7)
        p_a.add_argument('--severity', type=str, choices=['low', 'medium', 'high'])
        p_a.add_argument('--type', type=str, dest='anomaly_type',
                         choices=['spike', 'manipulation', 'cyclic'])
        p_a.add_argument('--category', type=str)
        p_a.add_argument('--json', action='store_true', help='Вывод в JSON')
        p_a.add_argument('--out', type=str, help='Сохранить в файл')

        # --- clusters ---
        p_c = sub.add_parser('clusters', help='Кластеризация товаров')
        p_c.add_argument('--category', type=str)
        p_c.add_argument('--clusters', type=int, default=4)

        # --- index ---
        p_i = sub.add_parser('index', help='Индекс цен по категориям')
        p_i.add_argument('--period', type=int, default=7, help='Период сравнения (дни)')

        # --- heatmap ---
        p_h = sub.add_parser('heatmap', help='Тепловая карта цен')
        p_h.add_argument('--category', type=str)
        p_h.add_argument('--days', type=int, default=7)
        p_h.add_argument('--max', type=int, default=30, help='Макс. товаров')

        # --- forecast ---
        p_f = sub.add_parser('forecast', help='Прогноз цен (ARIMA)')
        p_f.add_argument('--category', type=str)
        p_f.add_argument('--product-id', type=int, help='Прогноз для одного товара')
        p_f.add_argument('--horizon', type=int, default=7, help='Горизонт прогноза (дни)')
        p_f.add_argument('--limit', type=int, help='Макс. товаров для прогноза')

        # --- sensitivity ---
        p_s = sub.add_parser('sensitivity', help='Чувствительность к курсу валюты')
        p_s.add_argument('--category', type=str)
        p_s.add_argument('--currency', type=str, default='USD', choices=['USD', 'EUR', 'CNY'])
        p_s.add_argument('--product-id', type=int)
        p_s.add_argument('--limit', type=int, default=50)

        # --- metrics ---
        p_m = sub.add_parser('metrics', help='Метрики парсинга')
        p_m.add_argument('--days', type=int, default=7)

        # --- deals ---
        p_d = sub.add_parser('deals', help='Самые выгодные товары')
        p_d.add_argument('--days', type=int, default=30, help='Период для анализа')
        p_d.add_argument('--category', type=str)
        p_d.add_argument('--limit', type=int, default=20)

        # --- compare ---
        p_cmp = sub.add_parser('compare', help='Сравнение товаров')
        p_cmp.add_argument('ids', nargs='+', type=int, help='ID товаров через пробел')
        p_cmp.add_argument('--days', type=int, default=30)

        # --- cbr ---
        p_cbr = sub.add_parser('cbr', help='Загрузка курсов ЦБ РФ')
        p_cbr.add_argument('--backfill', type=int, help='Загрузить курсы за N дней назад')

        # --- save-snapshot ---
        p_ss = sub.add_parser('save-snapshot', help='Сохранить снимок аналитики в БД')
        p_ss.add_argument(
            '--kind',
            type=str,
            default='full',
            choices=['full', 'clusters', 'index', 'metrics', 'deals', 'anomalies'],
            help='full — полный дашборд; остальное — один тип отчёта.',
        )
        p_ss.add_argument('--period', type=int, default=7, help='Период индекса/аномалий (дни)')
        p_ss.add_argument('--metrics-days', type=int, default=7)
        p_ss.add_argument('--deals-days', type=int, default=30)
        p_ss.add_argument('--category', type=str, help='Для clusters/deals')
        p_ss.add_argument('--clusters', type=int, default=4)

        # --- list-snapshots ---
        p_ls = sub.add_parser('list-snapshots', help='Показать последние снимки из БД')
        p_ls.add_argument('--limit', type=int, default=10)
        p_ls.add_argument(
            '--kind',
            type=str,
            help='Фильтр по полю kind в БД (например full_dashboard); алиас: full = full_dashboard.',
        )

    # Имена субкоманд с дефисом нельзя сопоставить с методом через f'_handle_{report}'.
    _REPORT_HANDLER = {
        'save-snapshot': '_handle_save_snapshot',
        'list-snapshots': '_handle_list_snapshots',
    }

    def handle(self, *args: Any, **options: Any) -> None:
        report = options.get('report')
        if not report:
            self.stderr.write(self.style.ERROR(
                'Укажите тип отчёта: anomalies | clusters | index | heatmap | '
                'forecast | sensitivity | metrics | deals | compare | cbr | '
                'save-snapshot | list-snapshots'
            ))
            return
        method_name = self._REPORT_HANDLER.get(report, f'_handle_{report}')
        handler = getattr(self, method_name, None)
        if handler:
            handler(options)
        else:
            self.stderr.write(self.style.ERROR(f'Неизвестный отчёт: {report}'))

    # ------------------------------------------------------------------ #
    def _handle_anomalies(self, opts: dict) -> None:
        from apps.analytics.reports import generate_report, report_to_json, report_to_text

        entries = generate_report(
            days=opts.get('days', 7),
            severity=opts.get('severity'),
            anomaly_type=opts.get('anomaly_type'),
            category_slug=opts.get('category'),
        )
        if opts.get('json'):
            output = report_to_json(entries)
        else:
            output = report_to_text(entries)

        out_path = opts.get('out')
        if out_path:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(output)
            self.stdout.write(self.style.SUCCESS(f'Отчёт сохранён: {out_path}'))
        else:
            self.stdout.write(output)

    # ------------------------------------------------------------------ #
    def _handle_clusters(self, opts: dict) -> None:
        from apps.analytics.clustering import cluster_products

        clusters = cluster_products(
            category_slug=opts.get('category'),
            n_clusters=opts.get('clusters', 4),
        )
        for label, items in clusters.items():
            self.stdout.write(self.style.NOTICE(f'\n--- {label.upper()} ({len(items)} товаров) ---'))
            for f in sorted(items, key=lambda x: -x.volatility)[:15]:
                self.stdout.write(
                    f'  {f.product_name[:55]:55} | '
                    f'ср.цена {f.mean_price:>10.0f} р. | '
                    f'волат. {f.volatility:.3f} | '
                    f'тренд {f.trend:+.1%} | '
                    f'макс.скачок {f.max_change_pct:.1%} | '
                    f'записей {f.num_records}'
                )
            if len(items) > 15:
                self.stdout.write(f'  ... и ещё {len(items) - 15}')

    # ------------------------------------------------------------------ #
    def _handle_index(self, opts: dict) -> None:
        from apps.analytics.price_index import compute_category_index

        indices = compute_category_index(period_days=opts.get('period', 7))
        if not indices:
            self.stdout.write(self.style.WARNING('Нет данных для индекса цен.'))
            return

        self.stdout.write(
            f'{"Категория":30} | {"Ср.цена":>10} | {"Медиана":>10} | '
            f'{"Δ ср.%":>8} | {"Δ мед.%":>8} | {"Товаров":>7}'
        )
        self.stdout.write('-' * 90)
        for idx in indices:
            mean_ch = f'{idx.mean_change_pct:+.1f}%' if idx.mean_change_pct is not None else '  н/д'
            med_ch = f'{idx.median_change_pct:+.1f}%' if idx.median_change_pct is not None else '  н/д'
            self.stdout.write(
                f'{idx.category_name[:30]:30} | '
                f'{idx.current_mean:>10.0f} | '
                f'{idx.current_median:>10.0f} | '
                f'{mean_ch:>8} | '
                f'{med_ch:>8} | '
                f'{idx.product_count:>7}'
            )

    # ------------------------------------------------------------------ #
    def _handle_heatmap(self, opts: dict) -> None:
        from apps.analytics.heatmap import build_heatmap

        dates, rows = build_heatmap(
            category_slug=opts.get('category'),
            days=opts.get('days', 7),
            max_products=opts.get('max', 30),
        )
        if not rows:
            self.stdout.write(self.style.WARNING('Нет данных для тепловой карты.'))
            return

        header_dates = ' | '.join(f'{d:%d.%m}' for d in dates)
        self.stdout.write(f'{"Товар":40} | {header_dates}')
        self.stdout.write('-' * (42 + len(dates) * 8))

        for row in rows:
            cells_str = ' | '.join(f'{c.indicator:>6}' for c in row.cells)
            name = row.product_name[:40]
            self.stdout.write(f'{name:40} | {cells_str}')

    # ------------------------------------------------------------------ #
    def _handle_forecast(self, opts: dict) -> None:
        from apps.analytics.forecasting import forecast_all, forecast_product
        from apps.products.models import Product

        product_id = opts.get('product_id')
        horizon = opts.get('horizon', 7)

        if product_id:
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Товар id={product_id} не найден'))
                return
            forecasts = forecast_product(product, horizon=horizon)
            if not forecasts:
                self.stdout.write(self.style.WARNING('Недостаточно данных для прогноза.'))
                return
            self.stdout.write(self.style.NOTICE(f'Прогноз для: {product.name}'))
            self.stdout.write(f'{"Дата":12} | {"Прогноз":>10} | {"Нижн.":>10} | {"Верхн.":>10}')
            self.stdout.write('-' * 50)
            for f in forecasts:
                low = f'{f.lower_bound:.0f}' if f.lower_bound else '  -'
                high = f'{f.upper_bound:.0f}' if f.upper_bound else '  -'
                self.stdout.write(
                    f'{f.forecast_date!s:12} | {f.predicted_price:>10.0f} | {low:>10} | {high:>10}'
                )
        else:
            result = forecast_all(
                category_slug=opts.get('category'),
                horizon=horizon,
                limit=opts.get('limit'),
            )
            self.stdout.write(self.style.SUCCESS(
                f'Прогнозы: создано {result["forecasts_created"]}, ошибок {result["errors"]}'
            ))

    # ------------------------------------------------------------------ #
    def _handle_sensitivity(self, opts: dict) -> None:
        from apps.analytics.currency_sensitivity import (
            analyze_category_sensitivity,
            analyze_product_sensitivity,
        )
        from apps.products.models import Product

        currency = opts.get('currency', 'USD')
        product_id = opts.get('product_id')

        if product_id:
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Товар id={product_id} не найден'))
                return
            r = analyze_product_sensitivity(product, currency)
            if not r:
                self.stdout.write(self.style.WARNING('Недостаточно данных для анализа.'))
                return
            self.stdout.write(self.style.NOTICE(f'Товар: {r.product_name}'))
            self.stdout.write(r.detail)
        else:
            results = analyze_category_sensitivity(
                category_slug=opts.get('category'),
                currency_code=currency,
                limit=opts.get('limit', 50),
            )
            if not results:
                self.stdout.write(self.style.WARNING('Нет данных для анализа.'))
                return
            self.stdout.write(
                f'{"Товар":45} | {"Корр.":>6} | {"p-value":>8} | {"Точек":>5} | Вывод'
            )
            self.stdout.write('-' * 100)
            for r in results:
                self.stdout.write(
                    f'{r.product_name[:45]:45} | {r.correlation:>+6.3f} | '
                    f'{r.p_value:>8.4f} | {r.sample_size:>5} | {r.conclusion}'
                )

    # ------------------------------------------------------------------ #
    def _handle_metrics(self, opts: dict) -> None:
        from apps.analytics.parsing_metrics import compute_parsing_metrics

        s = compute_parsing_metrics(days=opts.get('days', 7))
        self.stdout.write(self.style.NOTICE(f'Метрики парсинга ({s.period_label})'))
        self.stdout.write(f'  Записей цен:            {s.total_price_records}')
        self.stdout.write(f'  Обновлено товаров:      {s.unique_products_updated}')
        self.stdout.write(f'  Всего товаров (активных):{s.total_products}')
        self.stdout.write(f'  Активных категорий:     {s.active_categories}')
        self.stdout.write(f'  Ср. записей/товар:      {s.avg_records_per_product}')
        self.stdout.write(f'  Товаров без данных:     {s.products_without_data}')
        if s.first_record:
            self.stdout.write(f'  Первая запись:          {s.first_record:%Y-%m-%d %H:%M}')
        if s.last_record:
            self.stdout.write(f'  Последняя запись:       {s.last_record:%Y-%m-%d %H:%M}')

    # ------------------------------------------------------------------ #
    def _handle_deals(self, opts: dict) -> None:
        from apps.analytics.best_deals import find_best_deals

        deals = find_best_deals(
            days=opts.get('days', 30),
            category_slug=opts.get('category'),
            limit=opts.get('limit', 20),
        )
        if not deals:
            self.stdout.write(self.style.WARNING('Выгодных предложений не найдено.'))
            return

        self.stdout.write(self.style.NOTICE(f'Самые выгодные товары ({len(deals)} шт.)'))
        self.stdout.write(
            f'{"Товар":45} | {"Цена":>8} | {"Мин.":>8} | {"Ср.":>8} | {"Скидка":>7} | Мин?'
        )
        self.stdout.write('-' * 95)
        for d in deals:
            is_min = '  ДА' if d.is_at_minimum else ''
            self.stdout.write(
                f'{d.product_name[:45]:45} | {d.current_price:>8.0f} | '
                f'{d.min_price:>8.0f} | {d.avg_price:>8.0f} | '
                f'{d.discount_from_avg_pct:>+6.1f}% | {is_min}'
            )

    # ------------------------------------------------------------------ #
    def _handle_compare(self, opts: dict) -> None:
        from apps.analytics.compare_products import compare

        ids = opts.get('ids', [])
        if not ids:
            self.stderr.write(self.style.ERROR('Укажите ID товаров: manage.py analytics_report compare 1 2 3'))
            return

        summaries = compare(ids, days=opts.get('days', 30))
        if not summaries:
            self.stdout.write(self.style.WARNING('Товары не найдены.'))
            return

        self.stdout.write(self.style.NOTICE('Сравнение товаров'))
        for s in summaries:
            self.stdout.write(f'\n  {s.name} (id={s.product_id})')
            self.stdout.write(f'    Категория:       {s.category}')
            self.stdout.write(f'    Текущая цена:    {s.current_price or "н/д"} руб.')
            self.stdout.write(f'    Мин. за {opts.get("days", 30)}д:    {s.min_price_30d or "н/д"} руб.')
            self.stdout.write(f'    Макс. за {opts.get("days", 30)}д:    {s.max_price_30d or "н/д"} руб.')
            self.stdout.write(f'    Средняя:         {s.avg_price_30d or "н/д"} руб.')
            ch = f'{s.change_30d_pct:+.1f}%' if s.change_30d_pct is not None else 'н/д'
            self.stdout.write(f'    Изменение:       {ch}')
            self.stdout.write(f'    Записей:         {s.records_count}')
            if s.forecast_7d:
                self.stdout.write(f'    Прогноз (7д):    {s.forecast_7d:.0f} руб. ({s.forecast_direction})')

    # ------------------------------------------------------------------ #
    def _handle_cbr(self, opts: dict) -> None:
        from apps.analytics.cbr_rates import backfill_rates, save_rates_for_date

        backfill = opts.get('backfill')
        if backfill:
            self.stdout.write(self.style.NOTICE(f'Загрузка курсов ЦБ за {backfill} дней...'))
            total = backfill_rates(days=backfill)
            self.stdout.write(self.style.SUCCESS(f'Загружено {total} новых курсов.'))
        else:
            created = save_rates_for_date()
            self.stdout.write(self.style.SUCCESS(f'Курсы за сегодня: {created} новых записей.'))

    # ------------------------------------------------------------------ #
    def _handle_save_snapshot(self, opts: dict) -> None:
        from apps.analytics.models import AnalyticsSnapshot
        from apps.analytics.snapshots import save_full_dashboard_snapshot, save_kind_snapshot

        kind = opts.get('kind', 'full')
        if kind == 'full':
            self.stdout.write(self.style.NOTICE('Считаем полный снимок (может занять минуту)...'))
            snap = save_full_dashboard_snapshot(
                period_days=opts.get('period', 7),
                metrics_days=opts.get('metrics_days', 7),
                deals_days=opts.get('deals_days', 30),
            )
            self.stdout.write(self.style.SUCCESS(
                f'Сохранён снимок id={snap.pk} ({snap.get_kind_display()}). '
                f'Краткая сводка: {snap.summary}'
            ))
            return

        mapping = {
            'clusters': AnalyticsSnapshot.Kind.CLUSTERS,
            'index': AnalyticsSnapshot.Kind.CATEGORY_INDEX,
            'metrics': AnalyticsSnapshot.Kind.PARSING_METRICS,
            'deals': AnalyticsSnapshot.Kind.DEALS_TOP,
            'anomalies': AnalyticsSnapshot.Kind.ANOMALIES_SUMMARY,
        }
        params: dict = {'period': opts.get('period', 7)}
        if opts.get('category'):
            params['category'] = opts['category']
        if kind == 'clusters':
            params['clusters'] = opts.get('clusters', 4)
        if kind == 'metrics':
            params['days'] = opts.get('metrics_days', 7)
        if kind == 'deals':
            params['days'] = opts.get('deals_days', 30)
            params['limit'] = 100
        if kind == 'anomalies':
            params['days'] = opts.get('period', 7)

        snap = save_kind_snapshot(mapping[kind], parameters=params)
        self.stdout.write(self.style.SUCCESS(
            f'Сохранён снимок id={snap.pk} ({snap.get_kind_display()}). summary={snap.summary}'
        ))

    # ------------------------------------------------------------------ #
    def _handle_list_snapshots(self, opts: dict) -> None:
        from apps.analytics.models import AnalyticsSnapshot

        limit = max(int(opts.get('limit') or 10), 1)
        k = opts.get('kind')
        if k == 'full':
            k = AnalyticsSnapshot.Kind.FULL_DASHBOARD
        qs = AnalyticsSnapshot.objects.all().order_by('-created_at')
        if k:
            qs = qs.filter(kind=k)
        qs = list(qs[:limit])
        if not qs:
            self.stdout.write(self.style.WARNING('Снимков пока нет.'))
            return
        self.stdout.write(self.style.NOTICE(f'Последние снимки (до {limit}):'))
        for s in qs:
            self.stdout.write(
                f'  id={s.pk}  {s.kind}  {s.created_at:%Y-%m-%d %H:%M}  '
                f'summary={str(s.summary)[:120]}...'
            )
