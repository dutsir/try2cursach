from __future__ import annotations

import time
import re
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from apps.prices.ozon_parser import OzonParser, _normalize_ozon_category_url
from apps.products.models import CategoryListing

GENERIC_OZON_CATEGORY_SLUGS = {

    'elektronika-15500',
    'odezhda-obuv-i-aksessuary-7500',
    'dom-i-sad-14500',
    'krasota-i-zdorove-6500',
    'detyam-7000',
    'bytovaya-tehnika-10500',
}


class Command(BaseCommand):
    help = 'Проверяет, что все пути Ozon в CategoryListing ведут на живые категории.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--only',
            nargs='+',
            default=None,
            help='Список slug-ов категорий витрины, которые проверять '
                 '(по умолчанию — все записи Ozon).',
        )
        parser.add_argument(
            '--pause',
            type=float,
            default=4.0,
            help='Пауза между проверками, сек. (по умолчанию 4.0).',
        )
        parser.add_argument(
            '--fix',
            nargs='*',
            default=None,
            metavar='OLD=NEW',
            help='Пары old_path=new_path, которые сразу применить в БД до проверки.',
        )

    def handle(self, *args, **options):
        fixes = self._parse_fixes(options.get('fix'))
        if fixes:
            applied = 0
            for old, new in fixes.items():
                qs = CategoryListing.objects.filter(source='ozon', external_path=old)
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
            .filter(source='ozon', is_active=True)
            .select_related('category')
            .order_by('category__name')
        )
        only = options.get('only')
        if only:
            qs = qs.filter(category__slug__in=only)

        listings = list(qs)
        if not listings:
            self.stdout.write(self.style.WARNING('Нет активных Ozon-каталогов в CategoryListing.'))
            return

        self.stdout.write(f'Проверяю {len(listings)} каталогов Ozon…')
        parser = OzonParser()
        try:
            driver = parser._get_driver()
            parser._warmup(driver)

            broken: list[tuple[CategoryListing, str]] = []
            ok_count = 0

            for idx, cl in enumerate(listings, 1):
                base = _normalize_ozon_category_url(cl.external_path)
                if not base or 'ozon.ru' not in urlparse(base).netloc.lower():
                    self.stdout.write(self.style.ERROR(
                        f'[{idx}/{len(listings)}] {cl.category.name}: '
                        f'пустой/битый путь {cl.external_path!r}'
                    ))
                    broken.append((cl, 'невалидный путь'))
                    continue

                parser._driver_get(driver, base)
                time.sleep(2.0)

                chk = parser._check_block(driver)
                if chk.get('captcha') or chk.get('blocked'):
                    self.stdout.write(self.style.ERROR(
                        f'[{idx}/{len(listings)}] BLOCK {cl.category.name} '
                        f'(path={cl.external_path!r}) — {chk.get("reason")}. '
                        f'Разгадайте капчу вручную в окне Chrome и запустите снова.'
                    ))
                    broken.append((cl, f'капча/блок: {chk.get("reason")}'))
                    time.sleep(float(options['pause']))
                    continue

                try:
                    cur_url = (driver.current_url or '').strip()
                except Exception:
                    cur_url = ''
                try:
                    cur_path = (urlparse(cur_url).path or '').rstrip('/')
                except Exception:
                    cur_path = ''

                redirected_home = cur_path in ('', '/')
                redirected_search = cur_path.startswith('/search')

                try:
                    anchors_count = int(
                        driver.execute_script(
                            'return document.querySelectorAll('
                            '\'a[href*="/product/"]\').length;'
                        )
                    )
                except Exception:
                    anchors_count = 0

                if redirected_home or redirected_search or anchors_count == 0:
                    reason = (
                        'редирект на главную' if redirected_home
                        else 'редирект на поиск' if redirected_search
                        else 'нет карточек /product/ на странице'
                    )
                    self.stdout.write(self.style.ERROR(
                        f'[{idx}/{len(listings)}] BROKEN {cl.category.name} '
                        f'(path={cl.external_path!r}) — {reason}'
                    ))
                    broken.append((cl, reason))
                else:
                    slug = self._ozon_slug_from_path(cl.external_path or '')
                    if slug in GENERIC_OZON_CATEGORY_SLUGS:
                        reason = f'слишком общий раздел /category/{slug}/'
                        self.stdout.write(self.style.ERROR(
                            f'[{idx}/{len(listings)}] BROKEN {cl.category.name} '
                            f'(path={cl.external_path!r}) — {reason}'
                        ))
                        broken.append((cl, reason))
                        time.sleep(float(options['pause']))
                        continue
                    self.stdout.write(
                        f'[{idx}/{len(listings)}] OK {cl.category.name} '
                        f'(path={cl.external_path!r}, товаров на странице ≥ {anchors_count})'
                    )
                    ok_count += 1

                time.sleep(float(options['pause']))

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f'Живых: {ok_count} / {len(listings)}'))
            if broken:
                self.stdout.write(self.style.ERROR(f'Битых: {len(broken)}'))
                for cl, reason in broken:
                    self.stdout.write(
                        f'  - {cl.category.name} | source=ozon | '
                        f'external_path={cl.external_path!r} | {reason}'
                    )
                self.stdout.write('')
                self.stdout.write(
                    'Как чинить: откройте нужный раздел на ozon.ru руками, '
                    'скопируйте путь после https://www.ozon.ru/ (например '
                    '"category/noutbuki-15692/") и либо поправьте запись в '
                    'админке, либо запустите `--fix old=new`.'
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

    @staticmethod
    def _ozon_slug_from_path(path: str) -> str:
        m = re.search(r'category/([^/]+)/?$', (path or '').strip())
        return m.group(1) if m else ''
