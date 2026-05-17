from __future__ import annotations

import hashlib
import logging
import re
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from django.conf import settings
from django.db import connection

if TYPE_CHECKING:
    from .features import Features

logger = logging.getLogger(__name__)

_MODEL: Any = None
_MODEL_LOAD_FAILED = False

_CYRILLIC_RE = re.compile(r'[а-яё]', re.I)


_EMBEDDING_CACHE: dict[str, list[float]] = {}


def embedding_enabled() -> bool:
    return bool(getattr(settings, 'DEDUP_EMBEDDING_ENABLED', True))


def embedding_model_name() -> str:
    return str(
        getattr(
            settings,
            'DEDUP_EMBEDDING_MODEL',
            'intfloat/multilingual-e5-base',
        )
    )


def embedding_dimensions() -> int:
    return int(getattr(settings, 'DEDUP_EMBEDDING_DIM', 768))


def auto_merge_threshold() -> float:
    return float(getattr(settings, 'DEDUP_EMBEDDING_AUTO_THRESHOLD', 0.86))


def review_threshold() -> float:
    return float(getattr(settings, 'DEDUP_EMBEDDING_REVIEW_THRESHOLD', 0.75))


def _uses_e5_prefix() -> bool:
    name = embedding_model_name().lower()
    return 'e5' in name or 'multilingual-e5' in name


def _apply_model_prefix(text: str, role: Literal['query', 'passage']) -> str:
    if not text or not _uses_e5_prefix():
        return text
    low = text.lstrip().lower()
    if low.startswith('query:') or low.startswith('passage:'):
        return text
    prefix = 'query: ' if role == 'query' else 'passage: '
    return prefix + text


def _load_model() -> Any:
    global _MODEL, _MODEL_LOAD_FAILED
    if _MODEL_LOAD_FAILED:
        return None
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning(
            'sentence-transformers не установлен — embedding-матчинг отключён. '
            'pip install sentence-transformers'
        )
        _MODEL_LOAD_FAILED = True
        return None

    from pathlib import Path
    name = embedding_model_name()

    # Check if model_name is a local path (fine-tuned model)
    model_path = Path(name)
    if model_path.exists() and model_path.is_dir():
        try:
            _MODEL = SentenceTransformer(name)
            logger.info('Fine-tuned embedding-модель загружена (локально): %s', name)
            return _MODEL
        except Exception:
            logger.exception('Не удалось загрузить fine-tuned модель %s', name)
            _MODEL_LOAD_FAILED = True
            return None

    # Fall back to HuggingFace model
    try:
        _MODEL = SentenceTransformer(name)
        logger.info('Embedding-модель загружена (HuggingFace): %s', name)
    except Exception:
        logger.exception('Не удалось загрузить embedding-модель %s', name)
        _MODEL_LOAD_FAILED = True
        return None
    return _MODEL


def build_match_text(
    features: Features,
    raw_name: str = '',
    *,
    role: Literal['query', 'passage'] = 'query',
) -> str:
    parts: list[str] = []
    if features.brand:
        parts.append(features.brand)
    specs = features.specs or {}
    for key in ('cpu_family', 'gpu_family', 'ram_gb', 'storage_gb', 'screen_in', 'variant_key'):
        val = specs.get(key)
        if val not in (None, ''):
            parts.append(f'{key}={val}')
    if features.model_code:
        parts.append(features.model_code)
    name = (raw_name or features.clean_name or '').strip()
    if name:
        parts.append(name)
    body = ' | '.join(parts) if parts else (name or 'unknown')
    return _apply_model_prefix(body, role)


def encode_text(text: str) -> list[float] | None:
    if not text or not embedding_enabled():
        return None


    text_hash = hashlib.md5(text.encode()).hexdigest()
    if text_hash in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[text_hash]

    model = _load_model()
    if model is None:
        return None
    try:
        vec = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        result = [float(x) for x in vec]


        if len(_EMBEDDING_CACHE) < 2000:
            _EMBEDDING_CACHE[text_hash] = result

        return result
    except Exception:
        logger.debug('encode_text failed', exc_info=True)
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    dot = float(np.dot(va, vb))
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def embedding_for_features(features: Features, raw_name: str = '') -> list[float] | None:
    return encode_text(build_match_text(features, raw_name, role='query'))


def find_embedding_match(
    features: Features,
    *,
    category_id: int,
    raw_name: str = '',
    candidate_ids: list[int] | None = None,
) -> tuple[Any | None, float]:
    from pgvector.django import CosineDistance

    from ..models import Product

    query_vec = embedding_for_features(features, raw_name)
    if not query_vec:
        return None, 0.0

    qs = (
        Product.objects
        .filter(category_id=category_id, is_active=True)
        .exclude(match_embedding__isnull=True)
    )
    if candidate_ids:


        qs = qs.filter(pk__in=candidate_ids)
    elif features.brand:


        qs = qs.filter(brand=features.brand)

    qs = (
        qs.annotate(distance=CosineDistance('match_embedding', query_vec))
          .only('id', 'name', 'brand', 'vendor_code', 'category_id',
                'specs_fingerprint', 'merge_locked', 'match_embedding')
          .order_by('distance')[:10]
    )
    try:
        candidates = list(qs)
    except Exception:


        logger.warning('pgvector ORDER BY не сработал', exc_info=True)
        return None, 0.0

    if not candidates:
        return None, 0.0

    best = candidates[0]


    distance = float(getattr(best, 'distance', 0.0) or 0.0)
    similarity = max(0.0, 1.0 - distance)
    return best, similarity


def sync_product_embedding(product: Any, features: Features, raw_name: str = '') -> bool:
    if not embedding_enabled():
        return False
    passage_text = build_match_text(
        features, raw_name or product.name, role='passage',
    )
    vec = encode_text(passage_text)
    if not vec:
        return False
    product.match_embedding = vec
    product.save(update_fields=['match_embedding', 'updated_at'])
    return True


def pick_display_name(*names: str) -> str:
    cleaned = [re.sub(r'\s+', ' ', (n or '').strip()) for n in names if (n or '').strip()]
    if not cleaned:
        return ''
    for n in cleaned:
        if _CYRILLIC_RE.search(n):
            return n
    return cleaned[0]


def embedding_cache_stats() -> dict[str, int]:
    dim = embedding_dimensions()
    return {
        'cache_size': len(_EMBEDDING_CACHE),
        'cache_size_mb': len(_EMBEDDING_CACHE) * dim * 8 // (1024 * 1024),
    }


__all__ = (
    'auto_merge_threshold',
    'build_match_text',
    'cosine_similarity',
    'embedding_cache_stats',
    'embedding_dimensions',
    'embedding_enabled',
    'embedding_for_features',
    'embedding_model_name',
    'encode_text',
    'find_embedding_match',
    'pick_display_name',
    'review_threshold',
    'sync_product_embedding',
)
