from __future__ import annotations

import re
import time
from urllib.parse import quote_plus

from django.core.management.base import BaseCommand

from apps.prices.ozon_parser import OzonParser
from apps.products.models import Category, CategoryListing

GENERIC_OZON_CATEGORY_SLUGS = {

    'elektronika-15500',
    'odezhda-obuv-i-aksessuary-7500',
    'dom-i-sad-14500',
    'krasota-i-zdorove-6500',
    'detyam-7000',
    'bytovaya-tehnika-10500',
}


OZON_CATEGORY_JS = r"""
return (function () {
  var as = document.querySelectorAll('a[href*="/category/"]');
  var counts = Object.create(null);
  for (var i = 0; i < as.length; i++) {
    try {
      var u = new URL(as[i].href);
      if ((u.hostname || '').indexOf('ozon.ru') === -1) continue;
      var m = (u.pathname || '').match(/^\/category\/([^\/]+)\/?$/);
      if (!m) continue;
      var slug = m[1];
      if (slug === 'all') continue;
      counts[slug] = (counts[slug] || 0) + 1;
    } catch (e) {}
  }
  var arr = [];
  for (var k in counts) arr.push([k, counts[k]]);
  arr.sort(function (a, b) { return b[1] - a[1]; });
  return arr.slice(0, 10);
})();
"""


class Command(BaseCommand):
    help = 'Автоподбор external_path Ozon для категорий без активной привязки.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--only',
            nargs='+',
            default=None,
            help='Slug-и категорий витрины, которые обрабатывать (по умолчанию — все без Ozon).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Обработать не больше N категорий (для отладки). 0 = без лимита.',
        )
        parser.add_argument(
            '--pause',
            type=float,
            default=5.0,
            help='Пауза между запросами Ozon (сек). По умолчанию 5.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Записать найденные пути в CategoryListing. Без флага — dry-run.',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Перезаписывать уже существующие активные записи Ozon '
                 '(по умолчанию они пропускаются).',
        )
        parser.add_argument(
            '--min-anchors',
            type=int,
            default=2,
            help='Минимальное число ссылок на /category/<slug>/ в поиске, чтобы '
                 'признать кандидата правдоподобным. По умолчанию 2.',
        )
        parser.add_argument(
            '--min-products',
            type=int,
            default=10,
            help='Минимальное число карточек /product/ на странице категории, '
                 'чтобы признать её живой. По умолчанию 10.',
        )
        parser.add_argument(
            '--max-candidates',
            type=int,
            default=3,
            help='Сколько топ-кандидатов из поиска проверять (по умолчанию 3).',
        )

    def handle(self, *args, **options) -> None:
        only = options.get('only')
        limit = int(options.get('limit') or 0)
        pause = float(options.get('pause') or 5.0)
        apply_changes = bool(options.get('apply'))
        overwrite = bool(options.get('overwrite'))
        min_anchors = int(options.get('min_anchors') or 2)
        min_products = int(options.get('min_products') or 10)
        max_candidates = int(options.get('max_candidates') or 3)


        all_active = Category.objects.filter(is_active=True)
        leaves = [c for c in all_active if c.is_leaf]
        if only:
            leaves = [c for c in leaves if c.slug in set(only)]

        existing_ozon = {
            cl.category_id: cl
            for cl in CategoryListing.objects.filter(source='ozon').select_related('category')
        }

        queue: list[tuple[Category, CategoryListing | None]] = []
        for cat in leaves:
            cl = existing_ozon.get(cat.id)
            if cl and cl.is_active and (cl.external_path or '').strip() and not overwrite:
                continue
            queue.append((cat, cl))

        if not queue:
            self.stdout.write(self.style.SUCCESS(
                'Все листовые категории уже имеют активные Ozon-привязки. Нечего искать.'
            ))
            return

        if limit and len(queue) > limit:
            queue = queue[:limit]

        mode = 'APPLY (будем писать в БД)' if apply_changes else 'DRY-RUN (только показать)'
        self.stdout.write(
            f'Ищу Ozon-каталоги для {len(queue)} категорий. Режим: {mode}. '
            f'Пауза между запросами: {pause:.1f}с.'
        )

        parser = OzonParser()
        found: list[tuple[Category, str, int, int]] = []
        missing: list[tuple[Category, str]] = []

        try:
            driver = parser._get_driver()
            parser._warmup(driver)

            for idx, (cat, cl) in enumerate(queue, 1):
                self.stdout.write('')
                self.stdout.write(
                    self.style.NOTICE(
                        f'[{idx}/{len(queue)}] {cat.name} (slug={cat.slug}) '
                        f'{"— уже есть: " + (cl.external_path or "") if cl else ""}'
                    )
                )

                path, anchors, products, note = self._discover_for_category(
                    driver=driver,
                    parser=parser,
                    name=cat.name,
                    min_anchors=min_anchors,
                    min_products=min_products,
                    max_candidates=max_candidates,
                    pause=pause,
                )

                if not path:
                    self.stdout.write(self.style.ERROR(f'  ✗ не нашли: {note}'))
                    missing.append((cat, note))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {path}  (anchor≈{anchors}, /product/≈{products})'
                    ))
                    found.append((cat, path, anchors, products))


                time.sleep(pause)

        finally:
            parser.close()

        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS(
            f'Найдено: {len(found)} из {len(queue)}. '
            f'Не нашли: {len(missing)}.'
        ))

        if apply_changes and found:
            written = 0
            for cat, path, _anchors, _products in found:
                obj, created = CategoryListing.objects.update_or_create(
                    category=cat,
                    source='ozon',
                    defaults={'external_path': path, 'is_active': True},
                )
                written += 1
                self.stdout.write(
                    ('создано: ' if created else 'обновлено: ')
                    + f'{cat.slug} -> {path}'
                )
            self.stdout.write(self.style.SUCCESS(f'Записано в БД: {written} записей.'))
        elif found and not apply_changes:
            self.stdout.write(self.style.WARNING(
                'Dry-run: в БД ничего не записано. '
                'Перезапусти с --apply, если результаты устраивают.'
            ))

        if missing:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                'Не удалось найти автоматически — подсмотрите вручную на ozon.ru:'
            ))
            for cat, note in missing:
                self.stdout.write(f'  - {cat.slug} ({cat.name}) — {note}')

    def _discover_for_category(
        self,
        *,
        driver,
        parser: OzonParser,
        name: str,
        min_anchors: int,
        min_products: int,
        max_candidates: int,
        pause: float,
    ) -> tuple[str | None, int, int, str]:
        search_url = (
            f'https://www.ozon.ru/search/?text={quote_plus(name)}'
            f'&from_global=true'
        )
        try:
            parser._driver_get(driver, search_url)
        except Exception as e:
            return None, 0, 0, f'не открыли поиск: {e}'
        time.sleep(2.5)

        chk = parser._check_block(driver)
        if chk.get('captcha') or chk.get('blocked'):
            return None, 0, 0, f'капча/блок на поиске: {chk.get("reason")}'

        try:
            top = driver.execute_script(OZON_CATEGORY_JS)
        except Exception as e:
            return None, 0, 0, f'ошибка JS на поиске: {e}'

        if not top:
            return None, 0, 0, 'на странице поиска нет ссылок /category/'


        self.stdout.write('  топ-кандидаты:')
        for slug, cnt in top[:5]:
            self.stdout.write(f'    - /category/{slug}/  (anchor={cnt})')

        for raw in top[:max_candidates]:
            try:
                slug = str(raw[0])
                cnt = int(raw[1])
            except (TypeError, ValueError, IndexError):
                continue
            if cnt < min_anchors:

                return None, cnt, 0, (
                    f'лучший кандидат (/category/{slug}/) набрал только {cnt} '
                    f'ссылок (<{min_anchors})'
                )
            if slug in GENERIC_OZON_CATEGORY_SLUGS:
                self.stdout.write(self.style.WARNING(
                    f'    ! /category/{slug}/: слишком общий раздел, пропускаем'
                ))
                continue

            cat_url = f'https://www.ozon.ru/category/{slug}/'
            try:
                parser._driver_get(driver, cat_url)
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'    ! пропуск {slug}: не открыли ({e})'
                ))
                continue
            time.sleep(2.0)

            chk = parser._check_block(driver)
            if chk.get('captcha') or chk.get('blocked'):
                return None, cnt, 0, f'капча/блок на /category/{slug}/'

            try:
                products_count = int(driver.execute_script(
                    'return document.querySelectorAll('
                    '\'a[href*="/product/"]\').length;'
                ) or 0)
            except Exception:
                products_count = 0


            try:
                page_title = str(driver.title or '')
            except Exception:
                page_title = ''
            try:
                page_h1 = str(
                    driver.execute_script(
                        'var h=document.querySelector("h1"); return h ? (h.innerText || h.textContent || "") : "";'
                    )
                    or ''
                )
            except Exception:
                page_h1 = ''
            if not self._looks_relevant(name, f'{page_title} {page_h1}'):
                self.stdout.write(self.style.WARNING(
                    f'    ! /category/{slug}/: нерелевантный title/h1, пробуем следующего'
                ))
                time.sleep(pause)
                continue

            if products_count >= min_products:
                return f'category/{slug}/', cnt, products_count, 'ok'

            self.stdout.write(self.style.WARNING(
                f'    ! /category/{slug}/: всего {products_count} карточек '
                f'/product/ (<{min_products}), пробуем следующего'
            ))
            time.sleep(pause)

        return None, 0, 0, 'ни один топ-кандидат не прошёл верификацию'

    @staticmethod
    def _looks_relevant(query_name: str, page_text: str) -> bool:
        q_tokens = Command._tokens(query_name)
        p_tokens = Command._tokens(page_text)
        if not q_tokens:
            return True
        return bool(q_tokens & p_tokens)

    @staticmethod
    def _tokens(raw: str) -> set[str]:
        stop = {
            'для', 'под', 'and', 'the', 'with', 'without',
            'серверные', 'серверный', 'компьютерные', 'компьютерный',
        }
        out: set[str] = set()
        for token in re.findall(r'[A-Za-zА-Яа-я0-9]+', (raw or '').lower()):
            if len(token) < 4:
                continue
            if token in stop:
                continue
            out.add(token)
        return out
