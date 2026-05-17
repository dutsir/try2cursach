from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import IntegrityError, transaction
from django.db.models import Model

from apps.products.models import Offer, Product
from apps.products.services import (
    _extract_mpn_from_name,
    _looks_like_mpn,
    _numbers_contradict,
)

logger = logging.getLogger(__name__)


def _needs_backfill(vc: str) -> bool:
    v = (vc or '').strip()
    return (not v) or v.isdigit()


def _one_to_many_fields() -> list[Any]:
    fields: list[Any] = []
    for f in Product._meta.get_fields():
        if getattr(f, 'one_to_many', False) or getattr(f, 'one_to_one', False):

            if f.related_model is not None and getattr(f, 'field', None) is not None:
                fields.append(f)
    return fields


def _pick_canonical(group: list[Product]) -> Product:
    def key(p: Product) -> tuple[int, int, int]:
        return (p.offers.count(), len(p.name or ''), -p.pk)
    return max(group, key=key)


def _split_by_number_compat(products: list[Product]) -> list[list[Product]]:
    groups: list[list[Product]] = []
    for p in products:
        placed = False
        for g in groups:
            if all(not _numbers_contradict(p.name, q.name) for q in g):
                g.append(p)
                placed = True
                break
        if not placed:
            groups.append([p])
    return groups


class Command(BaseCommand):
    help = 'Бэкфилл Product.vendor_code=MPN и склейка дубликатов по MPN.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true', help='Реально менять БД.')
        parser.add_argument(
            '--only-backfill', action='store_true',
            help='Только заполнить vendor_code из имени, не склеивать.',
        )
        parser.add_argument(
            '--only-merge', action='store_true',
            help='Не трогать vendor_code, только склеить уже заполненные.',
        )
        parser.add_argument(
            '--category', type=str, default='',
            help='Slug категории — ограничить действия одной категорией.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        apply = bool(options['apply'])
        only_backfill = bool(options['only_backfill'])
        only_merge = bool(options['only_merge'])
        category_slug = (options.get('category') or '').strip()

        if only_backfill and only_merge:
            self.stderr.write(self.style.ERROR('--only-backfill и --only-merge взаимоисключающие.'))
            return

        mode = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(self.style.NOTICE(f'Режим: {mode}'))
        if category_slug:
            self.stdout.write(self.style.NOTICE(f'Область: категория {category_slug!r}'))

        if not only_merge:
            self._backfill(apply=apply, category_slug=category_slug)

        if not only_backfill:
            self._merge(apply=apply, category_slug=category_slug)

        self.stdout.write(self.style.SUCCESS('Готово.'))


    def _backfill(self, *, apply: bool, category_slug: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING('\n[1/2] Backfill MPN из имён'))
        qs = Product.objects.all()
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        to_update: list[Product] = []
        scanned = 0
        for p in qs.only('id', 'name', 'vendor_code').iterator(chunk_size=500):
            scanned += 1
            if not _needs_backfill(p.vendor_code):
                continue
            mpn = _extract_mpn_from_name(p.name)
            if not mpn or not _looks_like_mpn(mpn):
                continue
            if mpn == p.vendor_code:
                continue
            p.vendor_code = mpn[:100]
            to_update.append(p)

        self.stdout.write(f'  Просмотрено: {scanned}, к обновлению: {len(to_update)}')
        if to_update[:5]:
            self.stdout.write('  Примеры:')
            for p in to_update[:5]:
                self.stdout.write(
                    f'    id={p.pk}  vc="" -> {p.vendor_code!r}   name={p.name!r}'
                )
        if apply and to_update:
            with transaction.atomic():
                Product.objects.bulk_update(to_update, ['vendor_code'], batch_size=500)
            self.stdout.write(self.style.SUCCESS(f'  Обновлено: {len(to_update)}'))


    def _merge(self, *, apply: bool, category_slug: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING('\n[2/2] Склейка дубликатов по (category, MPN)'))

        qs = Product.objects.exclude(vendor_code='').only(
            'id', 'name', 'vendor_code', 'category_id',
        )
        if category_slug:
            qs = qs.filter(category__slug=category_slug)


        buckets: dict[tuple[int, str], list[Product]] = defaultdict(list)
        for p in qs.iterator(chunk_size=500):
            key = (p.category_id, (p.vendor_code or '').strip().upper())
            buckets[key].append(p)

        total_groups = 0
        total_merges = 0
        blocked_by_numbers = 0

        for (cat_id, mpn), group in buckets.items():
            if len(group) < 2:
                continue
            subgroups = _split_by_number_compat(group)
            non_trivial = [sg for sg in subgroups if len(sg) > 1]
            if len(subgroups) > 1 and any(len(sg) == 1 for sg in subgroups):

                blocked_by_numbers += sum(1 for sg in subgroups if len(sg) == 1)
            if not non_trivial:
                continue
            total_groups += len(non_trivial)

            for sg in non_trivial:
                canonical = _pick_canonical(sg)
                donors = [p for p in sg if p.pk != canonical.pk]
                self.stdout.write(
                    f'  [cat={cat_id} mpn={mpn}] '
                    f'canonical=id{canonical.pk} "{canonical.name[:80]}" '
                    f'<- {len(donors)} donor(s)'
                )
                for d in donors:
                    self.stdout.write(f'     donor id{d.pk}: "{d.name[:80]}"')
                if apply:
                    for d in donors:
                        self._merge_one(donor=d, canonical=canonical)
                        total_merges += 1

        self.stdout.write('')
        self.stdout.write(
            f'  Групп для склейки: {total_groups}, '
            f'подозрительных серий оставлено: {blocked_by_numbers}'
        )
        if apply:
            self.stdout.write(self.style.SUCCESS(f'  Слиты донеры: {total_merges}'))

    def _merge_one(self, *, donor: Product, canonical: Product) -> None:
        donor_id = donor.pk
        canonical_id = canonical.pk
        with transaction.atomic():


            donor_offer_urls = {
                (o.source, o.url): o
                for o in Offer.objects.filter(product=donor).only('id', 'source', 'url')
            }
            canon_urls = set(
                Offer.objects
                .filter(product=canonical)
                .values_list('source', 'url')
            )
            for key, donor_offer in donor_offer_urls.items():
                if key in canon_urls:
                    logger.info(
                        'merge: удаляем дубликат оффера %s у donor=%s '
                        '(уже есть у canonical=%s)', key, donor_id, canonical_id,
                    )
                    donor_offer.delete()

            for rel in _one_to_many_fields():
                model: type[Model] = rel.related_model
                fk_name = rel.field.name
                self._move_related(model, fk_name, donor, canonical)

            donor.delete()
        logger.info(
            'merge: удалён donor id=%s в пользу canonical id=%s',
            donor_id, canonical_id,
        )

    def _move_related(
        self,
        model: type[Model],
        fk_name: str,
        donor: Product,
        canonical: Product,
    ) -> None:

        try:
            with transaction.atomic():
                moved = (
                    model.objects
                    .filter(**{fk_name: donor})
                    .update(**{fk_name: canonical})
                )
        except IntegrityError as exc:
            logger.info(
                'merge: %s.%s — batch update конфликтует (%s), переходим к per-row',
                model.__name__, fk_name, exc.__class__.__name__,
            )
        else:
            if moved:
                logger.info('merge: %s.%s — перенесено %d', model.__name__, fk_name, moved)
            return


        moved = 0
        deduped = 0
        for obj in list(model.objects.filter(**{fk_name: donor})):
            try:
                with transaction.atomic():
                    setattr(obj, fk_name, canonical)
                    obj.save(update_fields=[fk_name])
                moved += 1
            except IntegrityError:
                try:
                    with transaction.atomic():
                        obj.delete()
                    deduped += 1
                except Exception as exc:
                    logger.warning(
                        'merge: %s id=%s не смогли ни перенести, ни удалить: %s',
                        model.__name__, getattr(obj, 'pk', '?'), exc,
                    )
        logger.info(
            'merge: %s.%s — перенесено %d, дублей удалено %d',
            model.__name__, fk_name, moved, deduped,
        )
