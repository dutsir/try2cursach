
from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.prices.models import PriceHistory
from apps.prices.stats import compute_product_price_stats

from .models import Category, Product


@require_GET
def catalog_index(request):
    per_cat = dict(
        Product.objects
        .filter(is_active=True)
        .values('category_id')
        .annotate(n=Count('id'))
        .values_list('category_id', 'n')
    )

    roots = list(
        Category.objects
        .filter(parent__isnull=True, is_active=True)
        .prefetch_related('children')
        .order_by('name')
    )

    groups: list[dict[str, Any]] = []
    for root in roots:

        child_rows: list[dict[str, Any]] = []
        for child in root.children.filter(is_active=True).order_by('name'):
            child_rows.append({
                'obj': child,
                'count': sum(per_cat.get(i, 0) for i in child.descendants_ids()),
            })
        total = sum(per_cat.get(i, 0) for i in root.descendants_ids())
        groups.append({
            'obj': root,
            'total': total,
            'children': child_rows,
            'is_leaf': not child_rows,
            'own_count': per_cat.get(root.pk, 0),
        })

    return render(request, 'catalog/index.html', {'groups': groups})


@require_GET
def category_detail(request, slug: str):
    category = get_object_or_404(
        Category.objects.prefetch_related('children'),
        slug=slug,
        is_active=True,
    )


    children = list(category.children.filter(is_active=True).order_by('name'))
    if children:
        per_cat = dict(
            Product.objects
            .filter(is_active=True)
            .values('category_id')
            .annotate(n=Count('id'))
            .values_list('category_id', 'n')
        )
        child_rows = [
            {'obj': c, 'count': sum(per_cat.get(i, 0) for i in c.descendants_ids())}
            for c in children
        ]
        return render(
            request,
            'catalog/category.html',
            {
                'category': category,
                'ancestors': category.ancestors(),
                'children': child_rows,
                'rows': [],
                'is_group': True,
            },
        )


    products = list(
        Product.objects
        .filter(category=category, is_active=True)
        .prefetch_related('offers')
        .order_by('-last_parsed_at', 'name')[:200]
    )


    product_ids = [p.pk for p in products]
    actuals = (
        PriceHistory.objects
        .filter(product_id__in=product_ids, is_actual=True)
        .select_related('offer')
    )
    price_by_offer: dict[int, PriceHistory] = {}
    price_by_product: dict[int, list[PriceHistory]] = defaultdict(list)
    for ph in actuals:
        if ph.offer_id:
            price_by_offer[ph.offer_id] = ph
        price_by_product[ph.product_id].append(ph)

    rows: list[dict[str, Any]] = []
    for p in products:
        prices = price_by_product.get(p.pk, [])
        valid = [x for x in prices if x.offer_id]
        if valid:
            in_stock = [x for x in valid if x.offer and x.offer.is_available]
            pool = in_stock if in_stock else valid
            best = min(pool, key=lambda x: x.price)
            best_price = best.price
            best_source = best.offer.get_source_display() if best.offer else ''
            best_url = best.offer.url if best.offer else p.url
            offers_count = len({x.offer_id for x in valid})
        elif prices:
            best = min(prices, key=lambda x: x.price)
            best_price = best.price
            best_source = dict(PriceHistory.Source.choices).get(best.source, best.source)
            best_url = p.url
            offers_count = 0
        else:
            best_price = None
            best_source = ''
            best_url = p.url
            offers_count = 0

        rows.append({
            'product': p,
            'best_price': best_price,
            'best_source': best_source,
            'best_url': best_url,
            'offers_count': offers_count,
        })


    rows.sort(key=lambda r: (r['best_price'] is None, r['best_price'] or 0))

    return render(
        request,
        'catalog/category.html',
        {
            'category': category,
            'ancestors': category.ancestors(),
            'children': [],
            'rows': rows,
            'is_group': False,
        },
    )


@require_GET
def product_detail(request, slug: str):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('offers'),
        slug=slug,
        is_active=True,
    )


    offer_rows: list[dict[str, Any]] = []
    for offer in product.offers.all().order_by('source'):
        last = (
            PriceHistory.objects
            .filter(offer=offer, is_actual=True)
            .order_by('-timestamp')
            .first()
        )
        offer_rows.append({
            'offer': offer,
            'price': last.price if last else None,
            'old_price': last.old_price if last and last.old_price else None,
            'last_timestamp': last.timestamp if last else offer.last_seen_at,
        })


    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in offer_rows:
        by_source[row['offer'].source].append(row)

    def _best_key(r: dict[str, Any]) -> tuple[int, int, int]:
        return (
            0 if r['offer'].is_available else 1,
            0 if r['price'] is not None else 1,
            int(r['price'] or 0),
        )

    deduped_rows: list[dict[str, Any]] = []
    for src, rows in by_source.items():
        rows_sorted = sorted(rows, key=_best_key)
        best = rows_sorted[0]
        best['alt_count'] = len(rows_sorted) - 1
        deduped_rows.append(best)
    offer_rows = deduped_rows

    offer_rows.sort(
        key=lambda r: (r['price'] is None, not r['offer'].is_available, r['price'] or 0)
    )


    best_price = next(
        (r['price'] for r in offer_rows if r['price'] is not None and r['offer'].is_available),
        None,
    )
    if best_price is None:
        best_price = next(
            (r['price'] for r in offer_rows if r['price'] is not None),
            None,
        )


    stats = compute_product_price_stats(product, current_price=best_price)


    history = (
        PriceHistory.objects
        .filter(product=product)
        .order_by('timestamp')[:400]
    )
    series: dict[str, list[dict]] = defaultdict(list)
    for ph in history:
        series[ph.source].append({
            'ts': ph.timestamp.isoformat(),
            'price': float(ph.price),
        })

    chart_series = [
        {
            'name': dict(PriceHistory.Source.choices).get(k, k),
            'source': k,
            'points': v,
        }
        for k, v in series.items()
    ]

    return render(
        request,
        'catalog/product.html',
        {
            'product': product,
            'offer_rows': offer_rows,
            'best_price': best_price,
            'chart_series': chart_series,
            'stats': stats,
        },
    )
