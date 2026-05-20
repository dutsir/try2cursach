"""Smoke-test для attach_product_to_family на живой БД.

Создаёт временный Product (или находит существующий), вызывает attach,
проверяет результат, откатывает изменения через транзакцию.
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.products.dedupe.family_service import attach_product_to_family
from apps.products.models import Category, Product, ProductFamily


class Command(BaseCommand):
    help = 'Smoke-test attach_product_to_family на реальной БД.'

    def handle(self, *args: Any, **opts: Any) -> None:
        out = self.stdout

        try:
            with transaction.atomic():
                self._scenario_existing_ssd_attach(out)
                self._scenario_cpu_no_family(out)
                self._scenario_idempotent(out)
                # Откатываем все изменения, чтобы smoke не загрязнял БД.
                raise _Rollback()
        except _Rollback:
            out.write(self.style.SUCCESS('\n=== Smoke OK, БД не изменена ==='))

    def _scenario_existing_ssd_attach(self, out: Any) -> None:
        out.write(self.style.MIGRATE_HEADING('\n[scenario 1] attach нового SSD'))
        cat = Category.objects.get(slug='ssd-nakopiteli')
        # Возьмём существующую family Samsung 870 EVO и создадим новый Product
        # 4TB для неё — он должен присоединиться, не создав вторую семью.
        existing_family = ProductFamily.objects.filter(
            category=cat, name__icontains='samsung 870 evo',
        ).first()
        if existing_family is None:
            out.write('  семья Samsung 870 EVO не найдена, пропуск')
            return

        n_families_before = ProductFamily.objects.filter(category=cat).count()
        p = Product.objects.create(
            name='8000 ГБ 2.5" SATA накопитель Samsung 870 EVO [MZ-77E8T0BW-SMOKE] [SATA]',
            slug='smoke-870evo-8tb',
            category=cat,
            brand='samsung',
            vendor_code='SMOKE-FAMILY-TEST-MPN',
            specs_fingerprint={'storage_gb': 8000},
            url='https://example.com/smoke-870evo-8tb',
        )
        out.write(f'  создан Product id={p.id}, family={p.family_id}')

        family = attach_product_to_family(p, category_slug='ssd-nakopiteli')
        p.refresh_from_db()
        n_families_after = ProductFamily.objects.filter(category=cat).count()

        out.write(f'  после attach: family={p.family_id}, name={family.name!r}')
        out.write(f'  семей до/после: {n_families_before} / {n_families_after}')
        out.write(f'  variant_specs={p.variant_specs}')
        out.write(f'  variant_key_hash={p.variant_key_hash[:12]}...')
        assert p.family_id == family.id, 'family не привязалась'
        assert p.variant_specs == {'storage_gb': 8000}
        assert n_families_after == n_families_before, (
            'новая семья не должна была создаться — Samsung 870 EVO уже есть'
        )
        out.write(self.style.SUCCESS('  OK: Product присоединён к существующей семье'))

    def _scenario_cpu_no_family(self, out: Any) -> None:
        out.write(self.style.MIGRATE_HEADING('\n[scenario 2] процессор — family остаётся None'))
        cat = Category.objects.get(slug='processory')
        p = Product.objects.create(
            name='Процессор Intel Core i5-13400F BOX [LGA 1700]',
            slug='smoke-cpu-i5',
            category=cat,
            brand='intel',
            vendor_code='SMOKE-CPU-FAMILY-TEST',
            specs_fingerprint={'cpu_family': 'core i5'},
            url='https://example.com/smoke-cpu-i5',
        )
        family = attach_product_to_family(p, category_slug='processory')
        p.refresh_from_db()
        assert family is None, 'family для процессора должна быть None'
        assert p.family_id is None
        out.write(self.style.SUCCESS('  OK: family=None для категории без variants'))

    def _scenario_idempotent(self, out: Any) -> None:
        out.write(self.style.MIGRATE_HEADING('\n[scenario 3] идемпотентность'))
        cat = Category.objects.get(slug='ssd-nakopiteli')
        p = Product.objects.create(
            name='999 ГБ SSD M.2 2280 WD Blue SN570 WDS-SMOKE-IDEMPOTENT',
            slug='smoke-wd-blue-idem',
            category=cat,
            brand='',
            vendor_code='SMOKE-IDEM-WD-MPN',
            specs_fingerprint={'storage_gb': 999},
            url='https://example.com/smoke-wd-blue-idem',
        )
        f1 = attach_product_to_family(p, category_slug='ssd-nakopiteli')
        n_before = ProductFamily.objects.count()
        f2 = attach_product_to_family(p, category_slug='ssd-nakopiteli')
        n_after = ProductFamily.objects.count()
        assert f1.id == f2.id
        assert n_before == n_after, 'повторный attach не должен создавать вторую семью'
        out.write(self.style.SUCCESS(f'  OK: повторный attach стабилен (семей: {n_after})'))


class _Rollback(Exception):
    """Сигнал что транзакцию надо откатить — изменения были тестовые."""
    pass
