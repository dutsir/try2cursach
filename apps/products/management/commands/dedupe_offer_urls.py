"""Схлопывание внутри-источниковых дублей, возникших из-за НЕнормализованного URL.

Исторические офферы DNS хранят URL с хвостовым слешем (".../materinskaa-plata/"),
а свежий парсинг прогоняет URL через normalize_offer_url (слеш срезается). В итоге
.filter(source, url=canonical) НЕ находит старый оффер и создаёт НОВЫЙ оффер +
НОВЫЙ Product. Один и тот же товар-листинг расщепляется на две карточки —
ровно то, на что жалуется пользователь («один товар, а три карточки»).

Это НЕ fuzzy-дедуп: офферы указывают на ОДИН И ТОТ ЖЕ URL (после нормализации) —
это буквально одно объявление. Схлопывание по URL — штатная логика «update by url»
из [[dedup-principle]], просто запоздавшая для исторических данных.

Что делает на каждую коллизию (source, canonical_url) с >1 оффером:
  - canonical_product = тот из товаров группы, у кого БОЛЬШЕ офферов (богаче карточка);
    при равенстве — меньший id (как правило, тот, что уже получил cross-source офферы).
  - canonical_offer = оффер группы, лежащий на canonical_product.
  - Свежайший по updated_at оффер отдаёт свою цену/наличие/картинку на canonical_offer.
  - PriceHistory дублей перецепляется на canonical_offer + canonical_product (история не теряется).
  - Дубль-офферы удаляются, их URL освобождается; canonical_offer.url := canonical_url.
  - Опустевшие товары-дубли сливаются в canonical через merge_products
    (после удаления их dns-оффера same-source guard уже не мешает).

Dry-run по умолчанию; запись — только с --apply.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.products.dedupe.merge import merge_products
from apps.products.dedupe.normalizer import normalize_offer_url
from apps.products.models import MergeAuditLog, Offer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Схлопывает внутри-источниковые дубли с одинаковым (после нормализации) URL.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true', help='Применить (по умолчанию dry-run).')
        parser.add_argument('--dry-run', action='store_true', help='Только показать (по умолчанию).')
        parser.add_argument('--source', default='', help='Ограничить источником (напр. dns).')
        parser.add_argument('--limit', type=int, default=0, help='Максимум групп (0 = без лимита).')

    def handle(self, *args: Any, **opts: Any) -> None:
        apply = bool(opts['apply'])
        src_filter = (opts['source'] or '').strip().lower()
        limit = int(opts['limit'])

        self.stdout.write(
            f'Режим: {"APPLY" if apply else "DRY-RUN"} | '
            f'источник={src_filter or "все"} | limit={limit or "∞"}',
        )

        qs = Offer.objects.all()
        if src_filter:
            qs = qs.filter(source=src_filter)

        # group offers by (source, canonical_url)
        groups: dict[tuple[str, str], list[int]] = defaultdict(list)
        pcount: Counter[int] = Counter()
        for o in qs.values('id', 'url', 'source', 'product_id'):
            canon = normalize_offer_url(o['url'], source=o['source']) or o['url']
            groups[(o['source'], canon)].append(o['id'])
        for pid in Offer.objects.values_list('product_id', flat=True):
            pcount[pid] += 1

        collisions = [(k, ids) for k, ids in groups.items() if len(ids) > 1]
        self.stdout.write(f'Коллизий (source+canon_url с >1 оффером): {len(collisions)}')

        stats = Counter()
        processed = 0
        for (source, canon_url), offer_ids in collisions:
            if limit and processed >= limit:
                break
            processed += 1
            try:
                with transaction.atomic():
                    res = self._collapse_group(source, canon_url, offer_ids, pcount, apply)
                for k, v in res.items():
                    stats[k] += v
            except Exception as exc:  # noqa: BLE001
                stats['errors'] += 1
                logger.exception('collapse failed for %s %s: %s', source, canon_url, exc)
                if processed <= 10:
                    self.stdout.write(self.style.ERROR(f'  ОШИБКА {source} {canon_url[:60]}: {exc}'))

        # После схлопывания коллизий нормализуем URL у ОДИНОЧНЫХ офферов со
        # «слешевым»/«грязным» url — иначе следующий парсинг (он гонит url через
        # normalize_offer_url) не найдёт их и снова создаст дубль.
        collision_offer_ids = {oid for _, ids in collisions for oid in ids}
        normalized = self._normalize_singletons(qs, collision_offer_ids, apply)
        stats['urls_normalized'] += normalized

        self.stdout.write('=== ГОТОВО ===')
        self.stdout.write(f'  Групп обработано:    {processed}')
        self.stdout.write(f'  Офферов удалено:     {stats["offers_deleted"]}')
        self.stdout.write(f'  Товаров слито:       {stats["products_merged"]}')
        self.stdout.write(f'  Слияний отклонено:   {stats["merge_blocked"]}')
        self.stdout.write(f'  PriceHistory перецеплено: {stats["history_repointed"]}')
        self.stdout.write(f'  URL нормализовано (одиночных): {stats["urls_normalized"]}')
        self.stdout.write(f'  Ошибок:              {stats["errors"]}')
        if not apply:
            self.stdout.write(self.style.WARNING('DRY-RUN. Запусти с --apply.'))

    def _normalize_singletons(
        self, qs: Any, collision_offer_ids: set[int], apply: bool,
    ) -> int:
        """Чинит url у офферов, не входящих в коллизии (их canon-url свободен)."""
        count = 0
        rows = qs.exclude(id__in=collision_offer_ids).values('id', 'url', 'source')
        for o in rows:
            canon = normalize_offer_url(o['url'], source=o['source']) or o['url']
            if canon == o['url']:
                continue
            count += 1
            if apply:
                try:
                    Offer.objects.filter(id=o['id']).update(url=canon)
                except Exception as exc:  # noqa: BLE001 — на случай редкой constraint-гонки
                    logger.warning('url normalize skipped for offer %s: %s', o['id'], exc)
                    count -= 1
        return count

    def _collapse_group(
        self, source: str, canon_url: str, offer_ids: list[int],
        pcount: Counter[int], apply: bool,
    ) -> Counter[str]:
        from apps.prices.models import PriceHistory

        res: Counter[str] = Counter()
        offers = list(
            Offer.objects.select_for_update().filter(id__in=offer_ids),
        )
        if len(offers) < 2:
            return res

        # canonical product = больше всего офферов, затем меньший id
        def prod_rank(o: Offer) -> tuple[int, int]:
            return (-pcount[o.product_id], o.product_id)

        canonical_offer = min(offers, key=prod_rank)
        canonical_product_id = canonical_offer.product_id
        others = [o for o in offers if o.id != canonical_offer.id]

        # свежайший оффер отдаёт цену/наличие
        freshest = max(offers, key=lambda o: (o.updated_at or o.last_seen_at or o.id))

        if not apply:
            res['offers_deleted'] += len(others)
            dup_products = {o.product_id for o in others if o.product_id != canonical_product_id}
            res['products_merged'] += len(dup_products)
            return res

        # 1) перецепляем PriceHistory дублей на canonical_offer + canonical_product
        for o in others:
            moved = PriceHistory.objects.filter(offer=o).update(
                offer=canonical_offer, product=canonical_product_id,
            )
            res['history_repointed'] += moved

        # 2) удаляем дубль-офферы (освобождаем (source, url))
        for o in others:
            o.delete()
            res['offers_deleted'] += 1

        # 3) обновляем canonical_offer ценой свежайшего + нормализуем url
        if freshest.id != canonical_offer.id:
            canonical_offer.current_price = freshest.current_price
            canonical_offer.current_old_price = freshest.current_old_price
            canonical_offer.price_updated_at = freshest.price_updated_at
            canonical_offer.is_available = freshest.is_available
            if freshest.last_seen_at:
                canonical_offer.last_seen_at = freshest.last_seen_at
            if not canonical_offer.image_url and freshest.image_url:
                canonical_offer.image_url = freshest.image_url
        canonical_offer.url = canon_url
        canonical_offer.save(update_fields=[
            'current_price', 'current_old_price', 'price_updated_at',
            'is_available', 'last_seen_at', 'image_url', 'url',
        ])

        # 4) сливаем опустевшие товары-дубли в canonical
        dup_products = {o.product_id for o in others if o.product_id != canonical_product_id}
        for dup_pid in dup_products:
            mres = merge_products(
                canonical_product_id, dup_pid,
                actor=MergeAuditLog.Actor.AUTO,
                decision=MergeAuditLog.Decision.AUTO_MERGE,
                signals={'reason': 'offer_url_collapse', 'source': source},
                run_id='dedupe_offer_urls',
            )
            if mres.get('merged'):
                res['products_merged'] += 1
            else:
                res['merge_blocked'] += 1
                logger.warning(
                    'merge blocked %s<-%s: %s', canonical_product_id, dup_pid, mres.get('reason'),
                )
        return res
