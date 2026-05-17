from __future__ import annotations

import time
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from apps.prices.citilink_parser import (
    CITILINK_HOST,
    CitilinkParser,
    _normalize_catalog_url,
    _with_page_and_city,
)
from apps.products.models import CategoryListing


class Command(BaseCommand):
    help = 'Проверяет, что все slug-и Ситилинка в CategoryListing ведут на живые каталоги.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--only',
            nargs='+',
            default=None,
            help='Список slug-ов категорий нашей витрины, которые проверять '
                 '(по умолчанию — все записи Citilink).',
        )
        parser.add_argument(
            '--pause',
            type=float,
            default=3.0,
            help='Пауза между проверками, сек. (по умолчанию 3.0).',
        )
        parser.add_argument(
            '--fix',
            nargs='*',
            default=None,
            metavar='OLD=NEW',
            help='Пары old_slug=new_slug, которые сразу применить в БД до проверки. '
                 'Пример: --fix operativnaya-pamyat=moduli-pamyati',
        )

    def handle(self, *args, **options):
        fixes = self._parse_fixes(options.get('fix'))
        if fixes:
            applied = 0
            for old, new in fixes.items():
                qs = CategoryListing.objects.filter(source='citilink', external_path=old)
                for cl in qs:
                    cl.external_path = new
                    cl.save(update_fields=['external_path'])
                    applied += 1
                    self.stdout.write(self.style.WARNING(
                        f'fix: {cl.category.name} | {old} -> {new}'
                    ))
            self.stdout.write(f'Итого исправлено: {applied}')

        qs = (
            CategoryListing.objects
            .filter(source='citilink', is_active=True)
            .select_related('category')
            .order_by('category__name')
        )
        only = options.get('only')
        if only:
            qs = qs.filter(category__slug__in=only)

        listings = list(qs)
        if not listings:
            self.stdout.write(self.style.WARNING('Нет активных Citilink-каталогов в CategoryListing.'))
            return

        self.stdout.write(f'Проверяю {len(listings)} каталогов Ситилинка…')
        parser = CitilinkParser()
        try:
            driver = parser._get_driver()
            parser._warmup(driver)

            broken: list[tuple[CategoryListing, str]] = []
            ok_count = 0

            for idx, cl in enumerate(listings, 1):
                base = _normalize_catalog_url(cl.external_path)
                if not base or CITILINK_HOST not in urlparse(base).netloc.lower():
                    self.stdout.write(self.style.ERROR(
                        f'[{idx}/{len(listings)}] {cl.category.name}: пустой/битый путь {cl.external_path!r}'
                    ))
                    broken.append((cl, 'невалидный путь'))
                    continue

                url = _with_page_and_city(base, 1, parser._city_code)
                parser._driver_get(driver, url)
                time.sleep(1.0)
                try:
                    title = (driver.title or '').strip()
                except Exception:
                    title = ''
                low = title.lower()
                is_dead = (
                    ('404' in title and 'не найден' in low)
                    or '403' in title
                    or 'доступ запрещ' in low
                    or 'forbidden' in low
                    or 'access denied' in low
                )


                try:
                    cur_path = (urlparse(driver.current_url or '').path or '').rstrip('/')
                except Exception:
                    cur_path = ''
                redirected_home = cur_path in ('', '/')

                if is_dead or redirected_home:
                    reason = 'редирект на главную' if redirected_home else f'title={title!r}'
                    self.stdout.write(self.style.ERROR(
                        f'[{idx}/{len(listings)}] BROKEN {cl.category.name} '
                        f'(path={cl.external_path!r}) — {reason}'
                    ))
                    broken.append((cl, reason))
                else:
                    self.stdout.write(
                        f'[{idx}/{len(listings)}] OK {cl.category.name} '
                        f'(path={cl.external_path!r})'
                    )
                    ok_count += 1

                time.sleep(float(options['pause']))

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f'Живых: {ok_count} / {len(listings)}'))
            if broken:
                self.stdout.write(self.style.ERROR(f'Битых: {len(broken)}'))
                for cl, reason in broken:
                    self.stdout.write(
                        f'  - {cl.category.name} | source=citilink | '
                        f'external_path={cl.external_path!r} | {reason}'
                    )
                self.stdout.write('')
                self.stdout.write(
                    'Чтобы починить: открой раздел на citilink.ru руками, '
                    'скопируй часть URL после /catalog/ и до / (это и есть slug), '
                    'и либо отредактируй запись в админке, либо запусти '
                    '`python manage.py citilink_validate_listings --fix old=new`.'
                )
        finally:
            parser.close()

    @staticmethod
    def _parse_fixes(raw: list[str] | None) -> dict[str, str]:
        if not raw:
            return {}
        out: dict[str, str] = {}
        for item in raw:
            if '=' not in item:
                raise CommandError(f'Ожидался формат old=new, получено: {item!r}')
            old, new = item.split('=', 1)
            old = old.strip()
            new = new.strip()
            if not old or not new:
                raise CommandError(f'Пустая часть в --fix {item!r}')
            out[old] = new
        return out
