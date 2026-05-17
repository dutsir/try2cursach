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

    def key_hash(self) -> str:
        parts: list[str] = [self.brand or '', self.model_code or '']
        for k in ('ram_gb', 'storage_gb', 'screen_in', 'cpu_family', 'gpu_family', 'variant_key'):
            v = self.specs.get(k)
            if v is None or v == '':
                continue
            parts.append(f'{k}={v}')
        s = '|'.join(parts).lower()
        return hashlib.sha1(s.encode('utf-8')).hexdigest()


__all__ = ('Features',)
