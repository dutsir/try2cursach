from __future__ import annotations

import logging
import secrets
from collections import Counter
from datetime import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import models, transaction
from django.utils import timezone

from apps.products.dedupe.audit import enqueue_review, write_audit
from apps.products.dedupe.matcher import find_master
from apps.products.dedupe.merger import rollback_run
from apps.products.dedupe.normalizer import normalize_offer
from apps.products.models import MergeAuditLog, Offer, Product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Перепрогон матчинга по всем офферам с аудитом и rollback по run_id.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--apply', action='store_true', help='Реально менять product_id офферов.')
        parser.add_argument('--dry-run', action='store_true', help='Алиас по умолчанию.')
        parser.add_argument(
            '--category', type=str, default='',
            help='Slug категории — ограничить прогон одной категорией.',
        )
        parser.add_argument(
            '--threshold', type=float, default=None,
            help='Перекрыть AUTO_MERGE_THRESHOLD на этот прогон.',
        )
        parser.add_argument(
            '--with-features', action='store_true',
            help='Перед rebuild’ом перестроить normalized_features у офферов.',
        )
        parser.add_argument(
            '--rollback', type=str, default='',
            help='Откатить прогон по run_id. Игнорирует все остальные параметры.',
        )
        parser.add_argument(
            '--cooldown-hours', type=int, default=24,
            help='Cooldown в часах: оффер не двигаем между Product чаще этого окна.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        rollback_id = (options.get('rollback') or '').strip()
        if rollback_id:
            self.stdout.write(self.style.NOTICE(f'Rollback прогона {rollback_id!r}'))
            res = rollback_run(rollback_id)
            self.stdout.write(self.style.SUCCESS(
                f'Откачено офферов: {res["reverted"]}, пропущено: {res["skipped"]}'
            ))
            return

        apply = bool(options.get('apply'))
        category_slug = (options.get('category') or '').strip()
        threshold_override = options.get('threshold')


        if threshold_override is not None:
            from apps.products.dedupe import matcher as matcher_mod

            self.stdout.write(self.style.NOTICE(
                f'AUTO_MERGE_THRESHOLD перекрыт на {threshold_override:.2f}'
            ))
            matcher_mod.AUTO_MERGE_THRESHOLD = float(threshold_override)

        run_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + secrets.token_hex(3)
        mode = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(self.style.NOTICE(f'Режим: {mode}, run_id: {run_id}'))

        if options.get('with_features'):
            self.stdout.write('  Сначала перестраиваю normalized_features…')
            from django.core.management import call_command

            args = []
            if apply:
                args.append('--apply')
            if category_slug:
                args.extend(['--category', category_slug])
            call_command('rebuild_features', *args)

        self._rebuild(
            apply=apply,
            category_slug=category_slug,
            run_id=run_id,
            cooldown_hours=max(0, int(options.get('cooldown_hours') or 0)),
        )
        self.stdout.write(self.style.SUCCESS(f'\nГотово. run_id={run_id}'))

    def _is_offer_in_cooldown(self, offer: Offer, cooldown_hours: int) -> bool:
        if cooldown_hours <= 0:
            return False
        cutoff = timezone.now() - timezone.timedelta(hours=cooldown_hours)
        return MergeAuditLog.objects.filter(
            offer=offer,
            decision=MergeAuditLog.Decision.AUTO_MERGE,
            created_at__gte=cutoff,
        ).exclude(from_product_id=models.F('to_product_id')).exists()

    def _rebuild(
        self, *, apply: bool, category_slug: str, run_id: str, cooldown_hours: int,
    ) -> None:
        qs = Offer.objects.select_related('product', 'product__category').only(
            'id', 'product_id', 'source', 'url', 'source_sku', 'vendor_code',
            'raw_name', 'normalized_features', 'mpn_extracted',
            'product__name', 'product__category_id',
        )
        if category_slug:
            qs = qs.filter(product__category__slug=category_slug)

        decisions: Counter[str] = Counter()
        product_changes = 0
        scanned = 0
        orphan_candidates: set[int] = set()

        for offer in qs.iterator(chunk_size=500):
            scanned += 1
            current_product = offer.product
            if current_product is None:
                continue

            name = (offer.raw_name or '').strip() or current_product.name
            features = normalize_offer(
                name=name,
                source=offer.source,
                category_id=current_product.category_id,
                sku=offer.source_sku or offer.vendor_code or '',
                url=offer.url,
            )

            result = find_master(
                features,
                category_id=current_product.category_id,
                raw_name=name,
            )
            decisions[result.decision] += 1

            target_product = result.product
            decision_dec = {
                'auto_merge': MergeAuditLog.Decision.AUTO_MERGE,
                'review': MergeAuditLog.Decision.REVIEW,
                'new': MergeAuditLog.Decision.NEW,
            }.get(result.decision, MergeAuditLog.Decision.NEW)

            actor = MergeAuditLog.Actor.MIGRATION if apply else MergeAuditLog.Actor.SHADOW

            if (
                result.decision == 'auto_merge'
                and target_product is not None
                and target_product.pk != current_product.pk
            ):
                if self._is_offer_in_cooldown(offer, cooldown_hours):
                    decisions['cooldown_skipped'] += 1
                    write_audit(
                        offer=offer,
                        decision=MergeAuditLog.Decision.REVIEW,
                        actor=actor,
                        score=result.score,
                        signals={
                            **(result.signals or {}),
                            'rejected': 'cooldown_active',
                            'cooldown_hours': cooldown_hours,
                        },
                        from_product=current_product,
                        to_product=target_product,
                        run_id=run_id,
                    )
                    continue
                product_changes += 1
                if apply:
                    with transaction.atomic():
                        offer.product = target_product
                        offer.save(update_fields=['product', 'updated_at'])
                        write_audit(
                            offer=offer,
                            decision=decision_dec,
                            actor=actor,
                            score=result.score,
                            signals=result.signals,
                            from_product=current_product,
                            to_product=target_product,
                            run_id=run_id,
                        )
                    orphan_candidates.add(current_product.pk)
                else:
                    write_audit(
                        offer=offer,
                        decision=decision_dec,
                        actor=actor,
                        score=result.score,
                        signals=result.signals,
                        from_product=current_product,
                        to_product=target_product,
                        run_id=run_id,
                    )
            elif result.decision == 'review' and target_product is not None and target_product.pk != current_product.pk:
                if apply:
                    enqueue_review(
                        offer=offer,
                        suggested=target_product,
                        score=result.score,
                        signals=result.signals,
                    )
                write_audit(
                    offer=offer,
                    decision=decision_dec,
                    actor=actor,
                    score=result.score,
                    signals=result.signals,
                    from_product=current_product,
                    to_product=target_product,
                    run_id=run_id,
                )
            else:


                write_audit(
                    offer=offer,
                    decision=decision_dec,
                    actor=actor,
                    score=result.score,
                    signals=result.signals,
                    from_product=current_product,
                    to_product=target_product or current_product,
                    run_id=run_id,
                )

        self.stdout.write('')
        self.stdout.write(f'  Просмотрено офферов: {scanned}')
        for k, v in decisions.most_common():
            self.stdout.write(f'    {k}: {v}')
        self.stdout.write(f'  product_id изменён у: {product_changes}')

        if apply and orphan_candidates:
            removed = self._cleanup_orphans(orphan_candidates)
            self.stdout.write(f'  orphan Product удалено: {removed}')

    def _cleanup_orphans(self, candidate_ids: set[int]) -> int:
        removed = 0
        for pid in list(candidate_ids):
            try:
                p = Product.objects.get(pk=pid)
            except Product.DoesNotExist:
                continue
            if p.offers.exists():
                continue
            with transaction.atomic():
                p.delete()
            removed += 1
        return removed
