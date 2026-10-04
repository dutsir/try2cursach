"""L2 near-match merge: чинит under-merge, который tier-1 пропускает из-за
мусорного/несогласованного MPN (напр. citilink/mvideo пишут в vendor_code
описательные спец-токены вместо реального кода модели).

ЛОГИКА (см. apps/products/dedupe/matcher.l2_decide_merge):
  - Берём активные товары с готовым match_embedding, обновлённые за lookback.
  - Для каждого ищем ближайший по эмбеддингу товар того же бренда/категории.
  - sim>=auto_threshold и чистые гарды (magnet / specs / color / specific-MPN) и
    нет same-source overlap → AUTO-merge (более «богатый» офферами = canonical).
  - sim в [review,auto) ИЛИ same-source overlap → REVIEW-очередь.
  - конфликт гарда → skip (с причиной).

Эмбеддинги должны быть уже добиты (узел node3 / task_l2_dedup_sweep). Команда
их НЕ считает — только матчит и сливает.

Использование:
    python manage.py l2_dedup_merge                       # dry-run (по умолчанию)
    python manage.py l2_dedup_merge --lookback-hours 720  # шире окно
    python manage.py l2_dedup_merge --limit 500
    python manage.py l2_dedup_merge --apply               # реально сливает/ставит review
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser

from apps.prices.tasks import run_l2_merge_pass


class Command(BaseCommand):
    help = 'L2 near-match merge по эмбеддингам (под magnet/same-source/specs гардами).'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--lookback-hours', type=int, default=720,
                            help='Окно по updated_at (часы). По умолчанию 720 (30 дней).')
        parser.add_argument('--limit', type=int, default=500,
                            help='Максимум товаров для оценки за прогон.')
        parser.add_argument('--apply', action='store_true',
                            help='Реально сливать/ставить review (без флага — dry-run).')

    def handle(self, *args, **opts) -> None:
        dry_run = not opts['apply']
        stats = run_l2_merge_pass(
            lookback_hours=opts['lookback_hours'],
            limit=opts['limit'],
            dry_run=dry_run,
        )
        mode = 'DRY-RUN' if dry_run else 'APPLY'
        self.stdout.write(self.style.MIGRATE_HEADING(f'L2 merge [{mode}]'))
        self.stdout.write(f'  evaluated:       {stats["evaluated"]}')
        self.stdout.write(f'  auto_merged:     {stats["auto_merged"]}')
        self.stdout.write(f'  review_enqueued: {stats["review_enqueued"]}')
        self.stdout.write(f'  skipped:         {stats["skipped"]}')
        self.stdout.write(f'  no_candidate:    {stats["no_candidate"]}')
        if stats['samples']:
            self.stdout.write(self.style.MIGRATE_HEADING('  samples:'))
            for s in stats['samples']:
                self.stdout.write(
                    f'    [{s["decision"]:>10}] canon={s["canonical_id"]} '
                    f'dup={s["dup_id"]} sim={s["similarity"]} {s["reason"]}'
                )
        if dry_run:
            self.stdout.write(self.style.WARNING('dry-run: БД не изменена. Повтори с --apply.'))
        else:
            self.stdout.write(self.style.SUCCESS('Применено.'))
