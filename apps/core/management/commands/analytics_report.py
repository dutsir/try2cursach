from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = (
        'Аналитические отчёты: clusters | index | heatmap | metrics | deals | '
        'compare | save-snapshot | list-snapshots'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        sub = parser.add_subparsers(dest='report', help='Тип отчёта')

        p_c = sub.add_parser('clusters', help='Кластеризация товаров')
        p_c.add_argument('--category', type=str)
        p_c.add_argument('--clusters', type=int, default=4)

        p_i = sub.add_parser('index', help='Индекс цен по категориям')
        p_i.add_argument('--period', type=int, default=7, help='Период сравнения (дни)')

        p_h = sub.add_parser('heatmap', help='Тепловая карта цен')
        p_h.add_argument('--category', type=str)
        p_h.add_argument('--days', type=int, default=7)
        p_h.add_argument('--max', type=int, default=30, help='Макс. товаров')

        p_m = sub.add_parser('metrics', help='Метрики парсинга')
        p_m.add_argument('--days', type=int, default=7)

        p_d = sub.add_parser('deals', help='Самые выгодные товары')
        p_d.add_argument('--days', type=int, default=30, help='Период для анализа')
        p_d.add_argument('--category', type=str)
        p_d.add_argument('--limit', type=int, default=20)

        p_cmp = sub.add_parser('compare', help='Сравнение товаров')
        p_cmp.add_argument('ids', nargs='+', type=int, help='ID товаров через пробел')
        p_cmp.add_argument('--days', type=int, default=30)

        p_ss = sub.add_parser('save-snapshot', help='Сохранить снимок аналитики в БД')
        p_ss.add_argument(
            '--kind',
            type=str,
            default='full',
            choices=['full', 'clusters', 'index', 'metrics', 'deals'],
            help='full — полный дашборд; остальное — один тип отчёта.',
        )
        p_ss.add_argument('--period', type=int, default=7, help='Период индекса (дни)')
        p_ss.add_argument('--metrics-days', type=int, default=7)
        p_ss.add_argument('--deals-days', type=int, default=30)
        p_ss.add_argument('--category', type=str, help='Для clusters/deals')
        p_ss.add_argument('--clusters', type=int, default=4)

        p_ls = sub.add_parser('list-snapshots', help='Показать последние снимки из БД')
        p_ls.add_argument('--limit', type=int, default=10)
        p_ls.add_argument(
            '--kind',
            type=str,
            help='Фильтр по полю kind (например full_dashboard); алиас: full = full_dashboard.',
        )

    _REPORT_HANDLER = {
        'save-snapshot': '_handle_save_snapshot',
        'list-snapshots': '_handle_list_snapshots',
    }

    def handle(self, *args: Any, **options: Any) -> None:
        report = options.get('report')
        if not report:
            self.stderr.write(self.style.ERROR(
                'Укажите тип отчёта: clusters | index | heatmap | metrics | deals | '
                'compare | save-snapshot | list-snapshots'
            ))
            return
        method_name = self._REPORT_HANDLER.get(report, f'_handle_{report}')
        handler = getattr(self, method_name, None)
        if handler:
            handler(options)
        else:
            self.stderr.write(self.style.ERROR(f'Неизвестный отчёт: {report}'))

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

        snap = save_kind_snapshot(mapping[kind], parameters=params)
        self.stdout.write(self.style.SUCCESS(
            f'Сохранён снимок id={snap.pk} ({snap.get_kind_display()}). summary={snap.summary}'
        ))

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
