from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class Features:
    brand: str = ''
    model_code: str = ''
    model_code_source: str = ''
    specs: dict[str, Any] = field(default_factory=dict)
    clean_name: str = ''
    tokens: frozenset[str] = field(default_factory=frozenset)
    source: str = ''
    category_id: int | None = None
    source_sku: str = ''

    def to_jsonable(self) -> dict[str, Any]:
        return {
            'brand': self.brand,
            'model_code': self.model_code,
            'model_code_source': self.model_code_source,
            'specs': dict(self.specs),
            'clean_name': self.clean_name,
            'tokens': sorted(self.tokens),
            'source': self.source,
            'category_id': self.category_id,
            'source_sku': self.source_sku,
        }

    @classmethod
    def from_jsonable(cls, data: dict[str, Any]) -> 'Features':
        return cls(
            brand=data.get('brand', '') or '',
            model_code=data.get('model_code', '') or '',
            model_code_source=data.get('model_code_source', '') or '',
            specs=dict(data.get('specs') or {}),
            clean_name=data.get('clean_name', '') or '',
            tokens=frozenset(data.get('tokens') or []),
            source=data.get('source', '') or '',
            category_id=data.get('category_id'),
            source_sku=data.get('source_sku', '') or '',
        )

    @property
    def key_hash(self) -> str:
        """Хэш для группировки в FAMILY (общие для линейки модели).

        НЕ включает variant-специфичные поля (ram_gb, storage_gb для категорий
        где они являются вариантами). Это позволяет:
          - Kingston FURY DDR4 8GB и 16GB иметь один key_hash (одна family)
          - SSD Samsung 870 EVO 500GB и 1TB — одна family
          - Монитор LG 27UP650 и 32UP650 — одна family (разный screen_in)

        Variant поля (ram_gb, storage_gb, screen_in) попадают в variant_key
        конкретного Product, а не в family-уровень key_hash.

        cpu_family/gpu_family — общие для семьи (одна линейка процессоров).
        """
        parts: list[str] = [self.brand or '', self.model_code or '']
        # Только family-уровневые поля. Варианты (ram_gb, storage_gb, screen_in)
        # исключены — они отличают варианты внутри одной семьи.
        # cpu_family/gpu_family добавляются опционально, т.к. для ПК-сборок они
        # уже часть model_code.
        for k in ('cpu_family', 'gpu_family'):
            v = self.specs.get(k)
            if v is None or v == '':
                continue
            parts.append(f'{k}={v}')
        s = '|'.join(parts).lower()
        return hashlib.sha1(s.encode('utf-8')).hexdigest()

    @property
    def variant_key(self) -> str:
        """Хэш для конкретного варианта внутри семьи.

        Включает только variant-специфичные поля (ram_gb, storage_gb,
        screen_in). Используется чтобы различать варианты одной family.
        """
        parts: list[str] = []
        for k in ('ram_gb', 'storage_gb', 'screen_in', 'modules_count'):
            v = self.specs.get(k)
            if v is None or v == '':
                continue
            parts.append(f'{k}={v}')
        s = '|'.join(parts).lower()
        return hashlib.sha1(s.encode('utf-8')).hexdigest() if s else ''


__all__ = ('Features',)
