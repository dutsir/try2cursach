"""Чинит устаревшие Product.name, разошедшиеся с именем у живого оффера.

Симптом (жалоба пользователя): карточка «Ноутбук MAIBENBEN P429», а оффер на ней
давно перепарсился и торгует P625 — имя товара застряло на старой модели. Так бывает,
когда товар когда-то слили/перецепили, а имя не обновили; либо ранний парс записал
кривое имя. Живой путь (`_touch_product`) обновляет имя только на активном
перепарсинге — исторические рассинхроны он не лечит.

ВАЖНО — только ОДНО-офферные товары. У товара с единственным оффером имя ОБЯЗАНО
совпадать с этим оффером; расхождение модель-токенов = имя устарело, чиним. У
МНОГО-офферного товара расхождение со «свежайшим» оффером означает другое: на товаре
висит оффер другого варианта (мис-мёрдж / неверно перецепленный оффер), и
переименование это лишь ЗАМАСКИРУЕТ. Такие случаи тут НЕ трогаем (выводим счётчик
`multi_offer_divergent` для отдельного разбора).

Что делаем: для одно-офферного товара берём имя его оффера, выбираем отображаемое
через `pick_display_name` (кириллическое в приоритете) и сравниваем МОДЕЛЬНЫЕ ТОКЕНЫ
(`model_tokens` из cross_source — токены с цифрами: чип/модель/объём) текущего
Product.name с кандидатом. Расходятся → заменяем. Косметику (тот же набор модель-
токенов) не трогаем.

Dry-run по умолчанию; запись — только с --apply.
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.products.dedupe.cross_source import model_signature, model_tokens
from apps.products.dedupe.embedding import pick_display_name
from apps.products.models import Product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Обновляет устаревшие Product.name по имени свежайшего оффера.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true', help='Применить (по умолчанию dry-run).')
        parser.add_argument('--dry-run', action='store_true', help='Только показать (по умолчанию).')
        parser.add_argument('--category', default='', help='Ограничить слагом категории.')
        parser.add_argument('--limit', type=int, default=0, help='Максимум товаров (0 = без лимита).')
        parser.add_argument('--show', type=int, default=20, help='Сколько примеров напечатать.')

    def handle(self, *args: Any, **opts: Any) -> None:
        apply = bool(opts['apply'])
        cat = (opts['category'] or '').strip().lower()
        limit = int(opts['limit'])
        show = int(opts['show'])

        self.stdout.write(
            f'Режим: {"APPLY" if apply else "DRY-RUN"} | '
            f'категория={cat or "все"} | limit={limit or "∞"}',
        )

        qs = Product.objects.all().order_by('id')
        if cat:
            qs = qs.filter(category__slug=cat)

        fixed = 0
        scanned = 0
        printed = 0
        multi_divergent = 0
        for product in qs.iterator(chunk_size=500):
            if limit and fixed >= limit:
                break
            scanned += 1
            offers = list(
                product.offers.order_by('-last_seen_at', '-id')
                .values_list('raw_name', flat=True),
            )
            names = [n for n in offers if (n or '').strip()]
            if not names:
                continue
            candidate = pick_display_name(*names)
            if not candidate or candidate == product.name:
                continue
            # сравниваем именно модель-токены — косметику не трогаем
            cur_tok = model_tokens(model_signature(product.name, product.brand))
            new_tok = model_tokens(model_signature(candidate, product.brand))
            if not new_tok or cur_tok == new_tok:
                continue
            # МНОГО-офферный товар с расхождением — это НЕ устаревшее имя, а оффер
            # другого варианта на товаре (мис-мёрдж). Переименование замаскирует
            # проблему — НЕ трогаем, только считаем для отдельного разбора.
            if len(names) > 1:
                multi_divergent += 1
                continue
            fixed += 1
            if printed < show:
                printed += 1
                self.stdout.write(
                    f'  #{product.id} [{cur_tok or "∅"}→{new_tok}]\n'
                    f'      было:  {product.name[:80]}\n'
                    f'      стало: {candidate[:80]}',
                )
            if apply:
                product.name = candidate[:512]
                product.save(update_fields=['name', 'updated_at'])

        self.stdout.write('=== ГОТОВО ===')
        self.stdout.write(f'  Просмотрено товаров:        {scanned}')
        self.stdout.write(f'  Имён обновлено (одно-офф.):  {fixed}')
        self.stdout.write(f'  Много-офф. с расхожд. (НЕ трогаем): {multi_divergent}')
        if not apply:
            self.stdout.write(self.style.WARNING('DRY-RUN. Запусти с --apply.'))
