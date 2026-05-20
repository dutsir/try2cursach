from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from django.core.management.base import BaseCommand

from apps.products.dedupe.constants import get_variant_keys
from apps.products.dedupe.family import (
    compute_variant_key,
    derive_family_name,
    make_family_signature,
    split_specs,
)
from apps.products.models import Category, Product


class Command(BaseCommand):
    help = (
        'Read-only прогон: показывает как существующие Product разобьются на '
        'ProductFamily / Variant по правилам Этапа 2. БД не меняется.'
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--slugs', nargs='+', default=[
                'ssd-nakopiteli',
                'operativnaya-pamyat',
                'videokarty',
                'monitory',
                'processory',
            ],
            help='Какие категории показать',
        )
        parser.add_argument('--per-category', type=int, default=2000,
                            help='Сколько Product анализировать в категории')
        parser.add_argument('--sample', type=int, default=6,
                            help='Сколько мульти-вариантных семей показать примером')

    def handle(self, *args: Any, **opts: Any) -> None:
        for slug in opts['slugs']:
            self._report(slug, opts['per_category'], opts['sample'])

    def _spec_keys_for(self, slug: str) -> set[str]:
        keys: set[str] = set()
        qs = Product.objects.filter(category__slug=slug).only('specs_fingerprint')[:500]
        for p in qs:
            keys.update((p.specs_fingerprint or {}).keys())
        return keys

    def _report(self, slug: str, limit: int, sample_limit: int) -> None:
        out = self.stdout
        cat = Category.objects.filter(slug=slug).first()
        if cat is None:
            out.write(f'\n[{slug}] не найдена')
            return
        total = Product.objects.filter(category=cat).count()
        variant_keys = get_variant_keys(slug)
        all_spec_keys = self._spec_keys_for(slug)
        out.write(f'\n=== {slug} ({total} товаров) ===')
        out.write(f'  variant-правила:   {sorted(variant_keys) or "—"}')
        out.write(f'  встреченные specs: {sorted(all_spec_keys) or "(specs пусто у первых 500)"}')

        families: dict[str, list[Product]] = defaultdict(list)
        unrecognized = 0
        qs = Product.objects.filter(category=cat).only(
            'id', 'name', 'brand', 'vendor_code', 'specs_fingerprint',
        )[:limit]
        for p in qs:
            sig = make_family_signature(
                name=p.name, brand=p.brand or '',
                vendor_code=p.vendor_code or '',
                specs=p.specs_fingerprint, category_slug=slug,
            )
            if sig is None:
                # Категория без variants или модель не распознана.
                unrecognized += 1
                fk = f'solo-{p.id}'
            else:
                fk = sig['family_key']
            families[fk].append(p)
        if unrecognized:
            out.write(f'  без распознанной модели (одиночные): {unrecognized}')

        sizes = Counter(len(v) for v in families.values())
        multis = sorted(
            (v for v in families.values() if len(v) > 1),
            key=lambda v: -len(v),
        )
        out.write(f'  семей всего: {len(families)}; распределение по размеру: {dict(sorted(sizes.items()))}')
        out.write(f'  семей с >1 вариантом: {len(multis)}')

        for variants in multis[:sample_limit]:
            first = variants[0]
            family_name = derive_family_name(first.name)
            common, _ = split_specs(first.specs_fingerprint, slug)
            out.write(f'\n  [{len(variants)} вариантов] family: {family_name!r}')
            out.write(f'    brand={first.brand!r} mpn={first.vendor_code!r} common={common}')
            for v in variants[:4]:
                _, var = split_specs(v.specs_fingerprint, slug)
                vk = compute_variant_key(var)[:8]
                out.write(f'      - id={v.id} variant_specs={var} key={vk} name={v.name!r}')
            if len(variants) > 4:
                out.write(f'      ... и ещё {len(variants) - 4}')
