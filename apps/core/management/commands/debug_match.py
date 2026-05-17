from __future__ import annotations

from typing import Iterable

from django.core.management.base import BaseCommand, CommandParser

from apps.products.models import Offer, Product
from apps.products.services import _dice, _extract_mpn_from_name, _tokens


def _fmt_offer(o: Offer) -> str:
    return (
        f'    [{o.source:>8}] vc={o.vendor_code!r:<16}  '
        f'url={o.url}\n'
        f'             name(offer-side не храним, см. product.name)'
    )


def _resolve_products(
    *,
    product_id: int | None,
    slug: str | None,
    name: str | None,
    mpn: str | None,
) -> list[Product]:
    qs = Product.objects.select_related('category').prefetch_related('offers')
    if product_id:
        return list(qs.filter(pk=product_id))
    if slug:
        return list(qs.filter(slug__icontains=slug))
    if mpn:
        return list(qs.filter(vendor_code__iexact=mpn.strip()))
    if name:
        return list(qs.filter(name__icontains=name))
    return []


class Command(BaseCommand):
    help = 'Диагностика матчинга: что слиплось, что недоклеилось.'

    def add_arguments(self, parser: CommandParser) -> None:
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument('--product-id', type=int)
        g.add_argument('--slug', type=str, help='Подстрока slug (icontains).')
        g.add_argument('--name', type=str, help='Подстрока названия (icontains).')
        g.add_argument('--mpn', type=str, help='Точное совпадение vendor_code.')
        parser.add_argument(
            '--neighbors-dice', type=float, default=0.45,
            help='Порог dice для списка соседей (по умолчанию 0.45).',
        )
        parser.add_argument(
            '--neighbors-limit', type=int, default=8,
            help='Сколько соседей показывать (по умолчанию 8).',
        )

    def handle(self, *args, **options) -> None:
        products = _resolve_products(
            product_id=options.get('product_id'),
            slug=options.get('slug'),
            name=options.get('name'),
            mpn=options.get('mpn'),
        )
        if not products:
            self.stderr.write(self.style.ERROR('Не найдено ни одного Product по фильтру.'))
            return

        threshold = float(options.get('neighbors_dice', 0.45))
        limit = int(options.get('neighbors_limit', 8))

        for p in products:
            self._dump_product(p, threshold=threshold, limit=limit)
            self.stdout.write('')

    def _dump_product(self, p: Product, *, threshold: float, limit: int) -> None:
        out = self.stdout
        out.write(self.style.NOTICE('=' * 80))
        out.write(f'Product id={p.pk}  slug={p.slug}')
        out.write(f'  name={p.name!r}')
        out.write(f'  category={p.category.slug} (id={p.category_id})')
        out.write(f'  vendor_code (MPN в мастере)={p.vendor_code!r}')
        extracted = _extract_mpn_from_name(p.name)
        marker = '' if extracted == p.vendor_code else '  <-- отличается от vendor_code!'
        out.write(f'  _extract_mpn_from_name(name)={extracted!r}{marker}')

        offers: Iterable[Offer] = list(p.offers.order_by('source', 'pk'))
        out.write(f'  offers ({len(offers)}):')
        if not offers:
            out.write('    —')
        for o in offers:
            out.write(_fmt_offer(o))


        out.write('')
        out.write(f'  Соседи по категории (dice >= {threshold:.2f} или тот же vendor_code):')

        target_tokens = _tokens(p.name)
        neighbors: list[tuple[float, Product]] = []
        qs = (
            Product.objects
            .filter(category=p.category)
            .exclude(pk=p.pk)
            .only('id', 'name', 'vendor_code', 'slug')
        )
        for cand in qs[:2000]:
            same_mpn = bool(p.vendor_code) and cand.vendor_code.strip().lower() == p.vendor_code.strip().lower()
            score = _dice(target_tokens, _tokens(cand.name))
            if same_mpn or score >= threshold:
                neighbors.append((score, cand))
        neighbors.sort(key=lambda x: x[0], reverse=True)

        if not neighbors:
            out.write('    —  (подозрительных соседей нет)')
        else:
            for score, cand in neighbors[:limit]:
                cand_mpn = cand.vendor_code or '—'
                out.write(
                    f'    dice={score:.2f}  vc={cand_mpn!r:<16}  id={cand.pk}  '
                    f'name={cand.name!r}'
                )
