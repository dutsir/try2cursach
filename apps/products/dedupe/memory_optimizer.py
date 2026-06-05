"""
Оптимизация памяти при дедупликации больших категорий.

Проблема: При парсинге большой категории (мониторы, материнки)
может быть 200+ новых товаров. Дедупликация каждого товара
требует вычисления embeddings и поиска по pgvector, что
накапливает объекты в памяти → OOM.

Решение: Батчинг + кэширование результатов embedding'ов.
"""

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.products.models import Product

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """Кэш результатов embedding'ов в Redis (если доступен)."""

    def __init__(self):
        self.use_cache = getattr(settings, 'CACHE_EMBEDDINGS', True)
        self.ttl = getattr(settings, 'EMBEDDING_CACHE_TTL', 86400)  # 24 часа

    def make_key(self, category_id: int, raw_name: str) -> str:
        """Ключ для кэша embedding'а товара."""
        import hashlib
        hash_val = hashlib.md5(raw_name.encode()).hexdigest()[:8]
        return f'emb:cat{category_id}:{hash_val}:{raw_name[:20]}'

    def get(self, category_id: int, raw_name: str) -> list[float] | None:
        """Вернуть кэшированный embedding, если есть."""
        if not self.use_cache:
            return None
        try:
            key = self.make_key(category_id, raw_name)
            result = cache.get(key)
            if result:
                logger.debug('Embedding cache HIT: %s', key)
                return result
        except Exception as exc:
            logger.debug('Embedding cache read error: %s', exc)
        return None

    def set(self, category_id: int, raw_name: str, embedding: list[float]) -> None:
        """Закэшировать embedding товара."""
        if not self.use_cache:
            return
        try:
            key = self.make_key(category_id, raw_name)
            cache.set(key, embedding, self.ttl)
            logger.debug('Embedding cache SET: %s', key)
        except Exception as exc:
            logger.debug('Embedding cache write error: %s', exc)


embedding_cache = EmbeddingCache()


def clear_product_cache_for_category(category_id: int) -> None:
    """Очистить кэш эмбеддингов для категории при пересборке."""
    if not getattr(settings, 'CACHE_EMBEDDINGS', True):
        return
    try:
        # В реальной системе нужно отслеживать какие товары в какой категории
        # Пока просто логируем
        logger.info('Should clear embeddings for category %d', category_id)
    except Exception as exc:
        logger.debug('Error clearing embedding cache: %s', exc)


class DedupBatcher:
    """
    Обработчик товаров батчами для оптимизации памяти.

    Вместо того чтобы вызывать upsert_offer для каждого товара
    в цикле (что накапливает объекты в памяти), обрабатываем
    партиями и явно очищаем кэш между партиями.
    """

    def __init__(self, batch_size: int = 50):
        self.batch_size = max(10, min(batch_size, 200))

    def process_offers_in_batches(
        self,
        offers: list[dict[str, Any]],
        upsert_fn,
        *,
        collect_results: bool = False,
        **upsert_kwargs,
    ) -> dict[str, Any]:
        """
        Обработать список офферов батчами.

        Args:
            offers: Список офферов для обработки
            upsert_fn: Функция upsert_offer для обработки каждого оффера
            **upsert_kwargs: Дополнительные аргументы для upsert_fn

        Returns:
            Статистика обработки
        """
        stats = {
            'total': len(offers),
            'saved': 0,
            'new_offers': 0,
            'new_products': 0,
            'batches': 0,
            'errors': 0,
        }
        if collect_results:
            stats['rows'] = []

        for batch_idx in range(0, len(offers), self.batch_size):
            batch = offers[batch_idx:batch_idx + self.batch_size]
            stats['batches'] += 1

            try:
                batch_result = self._process_batch(
                    batch,
                    upsert_fn,
                    collect_results=collect_results,
                    **upsert_kwargs,
                )
                stats['saved'] += batch_result['saved']
                stats['new_offers'] += batch_result['new_offers']
                stats['new_products'] += batch_result['new_products']
                if collect_results:
                    stats['rows'].extend(batch_result.get('rows', []))
            except Exception as exc:
                logger.exception(
                    'Error processing batch %d (items %d-%d): %s',
                    stats['batches'],
                    batch_idx,
                    min(batch_idx + self.batch_size, len(offers)),
                    exc,
                )
                stats['errors'] += 1
                continue

            # Явно очищаем кэш Django между батчами чтобы избежать OOM
            self._clear_batch_cache()

            logger.info(
                'Batch %d/%d processed: saved=%d new_offers=%d new_products=%d',
                stats['batches'],
                (len(offers) + self.batch_size - 1) // self.batch_size,
                batch_result['saved'],
                batch_result['new_offers'],
                batch_result['new_products'],
            )

        return stats

    @staticmethod
    def _process_batch(
        batch: list[dict[str, Any]],
        upsert_fn,
        *,
        collect_results: bool = False,
        **kwargs,
    ) -> dict:
        """Обработать одну партию офферов."""
        result = {'saved': 0, 'new_offers': 0, 'new_products': 0}
        if collect_results:
            result['rows'] = []
        for item in batch:
            try:
                res = upsert_fn(**kwargs, **item)
                result['saved'] += 1
                if res.offer_created:
                    result['new_offers'] += 1
                if res.product_created:
                    result['new_products'] += 1
                if collect_results:
                    result['rows'].append({
                        'offer_id': res.offer.pk,
                        'source': item.get('source', ''),
                        'url': item.get('url', ''),
                        'name': item.get('name', ''),
                    })
            except Exception as exc:
                logger.debug('Error upserting offer %s: %s', item.get('name'), exc)
                if collect_results:
                    result['rows'].append({
                        'offer_id': None,
                        'source': item.get('source', ''),
                        'url': item.get('url', ''),
                        'name': item.get('name', ''),
                    })
                continue
        return result

    @staticmethod
    def _clear_batch_cache() -> None:
        """Очистить ORM кэш между батчами."""
        from django.db import reset_queries
        reset_queries()

        # Явно удалить большие объекты из памяти
        import gc
        try:
            # Не вызываем full garbage collection каждый раз,
            # только сборка поколения 0 (самые молодые объекты)
            gc.collect(generation=0)
        except Exception:
            pass


# Глобальный экземпляр для удобства
dedup_batcher = DedupBatcher(batch_size=50)
