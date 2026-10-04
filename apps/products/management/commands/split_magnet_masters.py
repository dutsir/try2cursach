"""Расклеивает «магниты» — мастер-Products, в которые слиплись офферы РАЗНЫХ
моделей (over-merge sink), включая WB.

КОНТЕКСТ: `split_oversized_masters` чинит только non-WB склейки (несколько офферов
одного источника = ошибка по url/sku). Но магниты бывают и на WB: один Product
охватывает много непересекающихся групп моделей (напр. JUHOR DDR4 разных частот,
Samsung SSD разных объёмов слиплись в один товар). Детектор `_is_magnet_canonical`
их уже не даёт пополнять (демоутит AUTO→REVIEW), а эта команда расклеивает
накопленное.

ЛОГИКА (совпадает с детектором `_disjoint_model_groups`):
  - Берём офферы магнита, считаем специфичные model-token'ы (`_is_specific_token`).
  - Union-find: офферы, делящие хотя бы один специфичный токен, — один компонент
    (= одна модель; для WB это разные продавцы ОДНОГО товара → остаются вместе).
  - Якорный компонент (с наибольшей суммарной историей цен) остаётся на мастере.
  - Каждый ДРУГОЙ компонент выносится в свой Product целиком (все офферы группы +
    их PriceHistory переезжают вместе).
  - Безгруппные офферы (без специфичного токена) остаются на мастере (консервативно:
    модель не распознана — не переносим вслепую).

Использование:
    python manage.py split_magnet_masters --dry-run            # по умолчанию
    python manage.py split_magnet_masters --apply
    python manage.py split_magnet_masters --apply --limit 20
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import Count

from apps.products.dedupe.matcher import (
    _is_magnet_canonical,
    _is_specific_token,
)
from apps.products.dedupe.normalizer import normalize_offer
from apps.products.dedupe.family_service import attach_product_to_family
from apps.products.models import Offer, Product

# Те же хелперы сигнатуры, что использует детектор (matcher импортирует их отсюда).
from apps.products.dedupe.cross_source import (
    model_tokens as _sig_model_tokens,
    model_signature as _model_signature,
)

logger = logging.getLogger(__name__)

_OFFER_SCAN_CAP = 80


class Command(BaseCommand):
    help = 'Расклеивает магниты (мастера с >=N непересекающимися группами моделей), включая WB.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true',
                            help='Применить изменения. По умолчанию dry-run.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Только показать что будет сделано (по умолчанию).')
        parser.add_argument('--category', type=str, default='',
                            help='Slug категории (без него — все).')
        parser.add_argument('--limit', type=int, default=0,
                            help='Максимум магнитов для обработки (0 = без лимита).')

    def handle(self, *args: Any, **options: Any) -> None:
        is_apply: bool = options.get('apply', False)
        category_slug: str = (options.get('category') or '').strip()
        limit: int = options.get('limit', 0) or 0

        self.stdout.write(self.style.NOTICE(
            f"Режим: {'APPLY' if is_apply else 'DRY-RUN'} | "
            f"категория={'все' if not category_slug else category_slug} | "
            f"limit={limit or '∞'}"
        ))

        magnets = self._find_magnets(category_slug)
        if limit:
            magnets = magnets[:limit]

        total = len(magnets)
        self.stdout.write(self.style.NOTICE(f"\nНайдено магнитов: {total}"))
        if total == 0:
            self.stdout.write(self.style.WARNING('Нечего расклеивать.'))
            return

        # Предварительный план (без записи): сколько компонентов/офферов вынесем.
        plan_groups_out = 0
        plan_offers_out = 0
        self.stdout.write('\nТоп-15 магнитов:')
        shown = 0
        for pid, reason in magnets:
            comps, ungrouped = self._components(pid)
            if len(comps) < 2:
                continue
            anchor_idx = self._anchor_index(comps)
            out = [c for i, c in enumerate(comps) if i != anchor_idx]
            plan_groups_out += len(out)
            plan_offers_out += sum(len(c['offer_ids']) for c in out)
            if shown < 15:
                p = Product.objects.filter(pk=pid).first()
                pname = (p.name[:50] if p else '?')
                self.stdout.write(
                    f"  product={pid} groups={len(comps)} ungrouped={len(ungrouped)} "
                    f"-> вынести компонентов={len(out)} офферов={sum(len(c['offer_ids']) for c in out)} "
                    f"| {reason} | {pname!r}"
                )
                shown += 1

        self.stdout.write(self.style.NOTICE(
            f"\nИтого к выносу: компонентов={plan_groups_out}, офферов={plan_offers_out}, "
            f"новых Products≈{plan_groups_out}"
        ))

        if not is_apply:
            self.stdout.write(self.style.WARNING(
                '\nDRY-RUN: ничего не изменилось. Запусти с --apply.'
            ))
            return

        self.stdout.write('\n=== APPLY ===')
        processed = comps_out = offers_out = new_products = errors = 0
        for i, (pid, reason) in enumerate(magnets, 1):
            try:
                stats = self._split_magnet(product_id=pid)
                processed += 1
                comps_out += stats['components_moved']
                offers_out += stats['offers_moved']
                new_products += stats['products_created']
                if i % 25 == 0:
                    self.stdout.write(
                        f"  [{i}/{total}] компонентов={comps_out} офферов={offers_out} "
                        f"Products={new_products}"
                    )
            except Exception as exc:
                errors += 1
                logger.exception('Ошибка split magnet product=%s: %s', pid, exc)

        self.stdout.write(self.style.SUCCESS(
            f'\n=== ГОТОВО ==='
            f'\n  Магнитов обработано: {processed}/{total}'
            f'\n  Компонентов вынесено: {comps_out}'
            f'\n  Офферов вынесено:    {offers_out}'
            f'\n  Products создано:    {new_products}'
            f'\n  Ошибок:              {errors}'
        ))

    # ------------------------------------------------------------------ helpers

    def _find_magnets(self, category_slug: str) -> list[tuple[int, str]]:
        qs = Offer.objects.values('product_id').annotate(n=Count('id')).filter(n__gte=2)
        cand_ids = [r['product_id'] for r in qs if r['product_id']]
        out: list[tuple[int, str]] = []
        for pid in cand_ids:
            p = Product.objects.filter(pk=pid).first()
            if not p:
                continue
            if category_slug and (not p.category or p.category.slug != category_slug):
                continue
            is_m, reason = _is_magnet_canonical(p)
            if is_m:
                out.append((pid, reason))
        return out

    def _components(self, product_id: int) -> tuple[list[dict[str, Any]], list[int]]:
        """Union-find офферов по специфичным токенам.

        Возвращает (components, ungrouped_offer_ids), где каждый component =
        {'offer_ids': [...], 'ph': суммарная история, 'rep': offer_id с макс PH}.
        """
        p = Product.objects.filter(pk=product_id).first()
        brand = (p.brand or '') if p else ''
        offers = list(
            Offer.objects.filter(product_id=product_id)
            .annotate(phc=Count('price_history'))
            .values('id', 'raw_name', 'phc')[:_OFFER_SCAN_CAP]
        )
        token_sets: list[frozenset[str]] = []
        idx_offer: list[dict[str, Any]] = []
        ungrouped: list[int] = []
        for o in offers:
            toks = _sig_model_tokens(_model_signature(o['raw_name'] or '', brand))
            specific = frozenset(t for t in toks if _is_specific_token(t))
            if specific:
                token_sets.append(specific)
                idx_offer.append(o)
            else:
                ungrouped.append(o['id'])

        if not token_sets:
            return [], ungrouped

        parent = {i: i for i in range(len(token_sets))}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        token_owner: dict[str, int] = {}
        for i, ts in enumerate(token_sets):
            for tok in ts:
                if tok in token_owner:
                    union(token_owner[tok], i)
                else:
                    token_owner[tok] = i

        comp_map: dict[int, dict[str, Any]] = {}
        for i, o in enumerate(idx_offer):
            root = find(i)
            c = comp_map.setdefault(root, {'offer_ids': [], 'ph': 0, 'rep': o['id'], 'rep_ph': -1})
            c['offer_ids'].append(o['id'])
            c['ph'] += o['phc']
            if o['phc'] > c['rep_ph']:
                c['rep_ph'] = o['phc']
                c['rep'] = o['id']
        return list(comp_map.values()), ungrouped

    @staticmethod
    def _anchor_index(comps: list[dict[str, Any]]) -> int:
        """Якорь — компонент с наибольшей суммарной историей (тай-брейк — больше офферов)."""
        best = 0
        for i, c in enumerate(comps):
            b = comps[best]
            if (c['ph'], len(c['offer_ids'])) > (b['ph'], len(b['offer_ids'])):
                best = i
        return best

    @transaction.atomic
    def _split_magnet(self, *, product_id: int) -> dict[str, int]:
        from apps.prices.models import PriceHistory

        master = Product.objects.select_for_update().filter(pk=product_id).first()
        if master is None:
            return {'components_moved': 0, 'offers_moved': 0, 'products_created': 0}

        comps, _ungrouped = self._components(product_id)
        if len(comps) < 2:
            return {'components_moved': 0, 'offers_moved': 0, 'products_created': 0}

        anchor_idx = self._anchor_index(comps)
        category = master.category
        stats = {'components_moved': 0, 'offers_moved': 0, 'products_created': 0}

        # Имя мастера могло быть генерик/чужой моделью; берём имя якорного оффера,
        # чтобы мастер был связным после расклейки.
        anchor_rep = Offer.objects.filter(pk=comps[anchor_idx]['rep']).first()
        if anchor_rep and anchor_rep.raw_name:
            from apps.products.dedupe.embedding import pick_display_name
            new_name = (pick_display_name(anchor_rep.raw_name) or anchor_rep.raw_name)[:512]
            if new_name and new_name != master.name:
                master.name = new_name
                master.save(update_fields=['name', 'updated_at'])

        for i, comp in enumerate(comps):
            if i == anchor_idx:
                continue
            rep = Offer.objects.filter(pk=comp['rep']).first()
            if rep is None:
                continue
            features = normalize_offer(
                name=rep.raw_name or master.name,
                source=rep.source,
                category_id=category.pk,
                sku=rep.source_sku or '',
                url=rep.url or '',
                mpn_hint=rep.mpn_extracted or '',
            )
            # Всегда создаём ОТДЕЛЬНЫЙ product без vendor_code, чтобы не схлопнуться
            # обратно в магнит по (category, brand, fake-MPN).
            new_product = self._standalone(features, offer=rep, category=category)

            for oid in comp['offer_ids']:
                off = Offer.objects.filter(pk=oid).first()
                if off is None:
                    continue
                off.product = new_product
                off.save(update_fields=['product', 'updated_at'])
                PriceHistory.objects.filter(offer=off).update(product=new_product)
                stats['offers_moved'] += 1

            attach_product_to_family(
                new_product,
                category_slug=category.slug if category else '',
                name=rep.raw_name or new_product.name,
                brand=features.brand,
                vendor_code=features.model_code,
                specs=features.specs,
            )
            stats['components_moved'] += 1
            stats['products_created'] += 1

        return stats

    def _standalone(self, features, *, offer: Offer, category) -> Product:
        from django.utils import timezone
        from apps.products.dedupe.services import _make_unique_slug
        from apps.products.dedupe.embedding import pick_display_name, sync_product_embedding

        name = offer.raw_name or features.brand or 'product'
        display = pick_display_name(name) or name
        product = Product.objects.create(
            name=display[:512],
            slug=_make_unique_slug(name, offer.source_sku or ''),
            category=category,
            vendor_code='',
            brand=(features.brand or '')[:64],
            specs_fingerprint=features.specs,
            key_hash=features.key_hash,
            url=offer.url or '',
            image_url=(offer.image_url or '')[:1024],
            is_active=True,
            last_parsed_at=timezone.now(),
        )
        sync_product_embedding(product, features, name)
        return product
