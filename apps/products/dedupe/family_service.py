"""DB-aware helper для двухуровневой дедупликации.

`family.py` остаётся чистым (без Django ORM), вся работа с БД — здесь.
"""
from __future__ import annotations

import logging
from typing import Any

from django.db import IntegrityError

from ..models import Product, ProductFamily
from .family import derive_family_name, make_family_signature

logger = logging.getLogger(__name__)


def attach_product_to_family(
    product: Product,
    *,
    category_slug: str,
    name: str = '',
    brand: str = '',
    vendor_code: str = '',
    specs: dict[str, Any] | None = None,
) -> ProductFamily | None:
    """Привязывает product к ProductFamily (создавая её при необходимости).

    Если категория не поддерживает варианты или модель не распознана —
    возвращает None, product.family остаётся прежним (обычно None).

    Идемпотентно: повторный вызов с теми же данными не делает save'ов.
    """
    sig = make_family_signature(
        name=name or product.name,
        brand=brand or (product.brand or ''),
        vendor_code=vendor_code or (product.vendor_code or ''),
        specs=specs if specs is not None else (product.specs_fingerprint or {}),
        category_slug=category_slug,
    )
    if sig is None:
        return None

    family = ProductFamily.objects.filter(family_key_hash=sig['family_key']).first()
    if family is None:
        try:
            family_name = sig['family_name'] or derive_family_name(product.name) or product.name
            family = ProductFamily.objects.create(
                name=family_name[:512],
                brand=(brand or product.brand or '')[:64],
                model_code=sig['model_code'][:128],
                category_id=product.category_id,
                common_specs=sig['common_specs'],
                family_key_hash=sig['family_key'],
            )
        except IntegrityError:
            family = ProductFamily.objects.filter(
                family_key_hash=sig['family_key'],
            ).first()
            if family is None:
                logger.warning(
                    'attach_to_family race: family disappeared after IntegrityError, key=%s',
                    sig['family_key'],
                )
                return None

    needs_update = (
        product.family_id != family.id
        or product.variant_key_hash != sig['variant_key']
        or (product.variant_specs or {}) != sig['variant_specs']
    )
    if needs_update:
        product.family = family
        product.variant_specs = sig['variant_specs']
        product.variant_key_hash = sig['variant_key']
        product.save(update_fields=[
            'family', 'variant_specs', 'variant_key_hash', 'updated_at',
        ])
    return family


__all__ = ('attach_product_to_family',)
