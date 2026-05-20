from __future__ import annotations

from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.products.models import Category, MergeAuditLog, Product, ProductFamily


class Command(BaseCommand):
    help = 'Краткая статистика по ProductFamily / Product.family.'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument('--sample', type=int, default=5,
                            help='Сколько крупнейших семей показать')

    def handle(self, *args: Any, **opts: Any) -> None:
        out = self.stdout
        total_products = Product.objects.count()
        with_family = Product.objects.filter(family__isnull=False).count()
        total_families = ProductFamily.objects.count()

        out.write(self.style.MIGRATE_HEADING('=== Сводка ==='))
        out.write(f'Product всего:          {total_products}')
        out.write(f'Product с family:       {with_family}')
        out.write(f'Product без family:     {total_products - with_family}')
        out.write(f'ProductFamily всего:    {total_families}')

        out.write(self.style.MIGRATE_HEADING('\n=== По категориям ==='))
        cats = Category.objects.annotate(
            n_products=Count('products', distinct=True),
            n_families=Count('families', distinct=True),
        ).order_by('-n_families')
        for c in cats:
            if c.n_families == 0 and c.n_products == 0:
                continue
            with_fam = Product.objects.filter(
                category=c, family__isnull=False,
            ).count()
            line = f'{c.slug:35s} products={c.n_products:5d}  families={c.n_families:4d}  с family={with_fam:5d}'
            out.write(line)

        out.write(self.style.MIGRATE_HEADING('\n=== Крупнейшие семьи ==='))
        top = (
            ProductFamily.objects
            .annotate(n_variants=Count('variants'))
            .order_by('-n_variants')[:opts['sample']]
        )
        for f in top:
            out.write(f'\n[{f.n_variants} вариантов] {f.name}')
            out.write(f'  brand={f.brand!r} model_code={f.model_code!r} common={f.common_specs}')
            for v in f.variants.all()[:5]:
                out.write(f'    - id={v.id} variant_specs={v.variant_specs} name={v.name[:80]!r}')
            if f.n_variants > 5:
                out.write(f'    ... ещё {f.n_variants - 5}')

        out.write(self.style.MIGRATE_HEADING('\n=== Audit log ==='))
        audit_counter = Counter(
            MergeAuditLog.objects
            .filter(signals__kind='family_backfill')
            .values_list('run_id', flat=True)
        )
        for run_id, n in audit_counter.most_common(5):
            out.write(f'  run_id={run_id}: {n} записей')
