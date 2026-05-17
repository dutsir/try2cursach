from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.prices.models import ParseRun
from apps.prices.tasks import _cleanup_stuck_parseruns


class Command(BaseCommand):
    help = (
        'Перевести зависшие ParseRun (status=RUNNING дольше N минут) в ERROR.'
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--timeout-minutes', type=int, default=None,
            help='Через сколько минут RUNNING считается зависшим '
                 '(default: settings.PARSE_RUN_STUCK_TIMEOUT_MINUTES=30).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Только показать список без обновления.',
        )

    def handle(self, *args, **opts) -> None:
        minutes = int(opts.get('timeout_minutes') or getattr(
            settings, 'PARSE_RUN_STUCK_TIMEOUT_MINUTES', 30,
        ))

        if opts.get('dry_run'):
            cutoff = timezone.now() - timedelta(minutes=minutes)
            stuck = (
                ParseRun.objects
                .filter(status=ParseRun.Status.RUNNING, started_at__lt=cutoff)
                .select_related('category')
            )
            count = stuck.count()
            if count == 0:
                self.stdout.write(self.style.SUCCESS(
                    f'dry-run: зависших ParseRun > {minutes} мин не найдено.'
                ))
                return
            self.stdout.write(self.style.WARNING(
                f'dry-run: найдено {count} зависших ParseRun (>{minutes} мин). '
                f'Первые 20:'
            ))
            for run in stuck.order_by('started_at')[:20]:
                cat = run.category.slug if run.category else '—'
                age = (timezone.now() - run.started_at).total_seconds() / 60
                self.stdout.write(
                    f'  id={run.pk} source={run.source} category={cat} '
                    f'started_at={run.started_at:%Y-%m-%d %H:%M} '
                    f'age={age:.0f} мин'
                )
            return

        result = _cleanup_stuck_parseruns(timeout_minutes=minutes)
        if result['cleaned']:
            self.stdout.write(self.style.SUCCESS(
                f"Помечено как ERROR: {result['cleaned']} ParseRun "
                f"(timeout={result['timeout_minutes']} мин)"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Зависших ParseRun > {minutes} мин не найдено.'
            ))
