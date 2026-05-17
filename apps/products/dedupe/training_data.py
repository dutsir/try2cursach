"""Extract and prepare training data from MergeAuditLog for fine-tuning embeddings."""
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional
from decimal import Decimal

from django.db.models import Q

from apps.products.models import MergeAuditLog, Offer, Product

logger = logging.getLogger(__name__)


@dataclass
class TrainingPair:
    """Single training pair for embedding fine-tuning."""
    offer_a_name: str
    offer_b_name: str
    offer_a_specs: str
    offer_b_specs: str
    offer_a_source: str
    offer_b_source: str
    label: int  # 1 = match, 0 = no match, -1 = uncertain
    score: float
    score_confidence: str  # 'high', 'medium', 'low'
    rule: Optional[str] = None
    signals: dict[str, Any] = None

    def to_dict(self):
        """Convert to dictionary, handling special types."""
        d = asdict(self)
        d['score'] = float(d['score'])
        return d


def _build_offer_text(offer: Offer) -> str:
    """Build text descriptor from offer."""
    parts = []

    if offer.raw_name:
        parts.append(offer.raw_name)

    if offer.normalized_features:
        nf = offer.normalized_features
        if nf.get('brand'):
            parts.append(nf['brand'])
        if nf.get('model_code'):
            parts.append(nf['model_code'])
        if nf.get('clean_name'):
            parts.append(nf['clean_name'])

        specs = nf.get('specs', {})
        if specs:
            spec_strs = []
            for key in ['cpu_family', 'gpu_family', 'ram_gb', 'storage_gb', 'screen_in', 'color']:
                val = specs.get(key)
                if val:
                    spec_strs.append(str(val))
            if spec_strs:
                parts.append(' '.join(spec_strs))

    return ' | '.join(parts)


def _get_score_confidence(score: float) -> str:
    """Classify score into confidence level."""
    if score >= 0.85:
        return 'high'
    elif score >= 0.65:
        return 'medium'
    else:
        return 'low'


def export_merge_audit_pairs(
    min_date=None,
    max_pairs: Optional[int] = None,
    include_weak: bool = True,
) -> list[TrainingPair]:
    """
    Export training pairs from MergeAuditLog.

    Args:
        min_date: Only include records after this date (datetime)
        max_pairs: Limit number of pairs to export
        include_weak: Include REVIEW decisions as weak labels (-1)

    Returns:
        List of TrainingPair objects
    """
    pairs = []

    # Query positive pairs (AUTO_MERGE decisions)
    positive_logs = MergeAuditLog.objects.filter(
        decision=MergeAuditLog.Decision.AUTO_MERGE,
        actor=MergeAuditLog.Actor.AUTO,
        reverted=False,
    )
    if min_date:
        positive_logs = positive_logs.filter(created_at__gte=min_date)

    # Group by to_product to find all offers merged together
    merged_groups = {}
    for log in positive_logs.select_related('offer', 'to_product'):
        if not log.offer or not log.to_product:
            continue
        product_id = log.to_product_id
        if product_id not in merged_groups:
            merged_groups[product_id] = []
        merged_groups[product_id].append(log.offer)

    # Create pairs from offers merged to same product
    for offers in merged_groups.values():
        for i, offer_a in enumerate(offers):
            for offer_b in offers[i + 1:]:
                # Skip pairs from same source (wouldn't help training)
                if offer_a.source == offer_b.source:
                    continue

                pair = TrainingPair(
                    offer_a_name=offer_a.raw_name or offer_a.product.name,
                    offer_b_name=offer_b.raw_name or offer_b.product.name,
                    offer_a_specs=_build_offer_text(offer_a),
                    offer_b_specs=_build_offer_text(offer_b),
                    offer_a_source=offer_a.source,
                    offer_b_source=offer_b.source,
                    label=1,  # Positive: should match
                    score=0.95,  # High confidence matches
                    score_confidence='high',
                    rule='auto_merge',
                    signals={'rule': 'auto_merge'},
                )
                pairs.append(pair)

    # Query negative pairs (Hard rejects)
    hard_rejects = MergeAuditLog.objects.filter(
        Q(signals__rejected__isnull=False),
        actor=MergeAuditLog.Actor.AUTO,
    )
    if min_date:
        hard_rejects = hard_rejects.filter(created_at__gte=min_date)

    rejected_offers = {}
    for log in hard_rejects.select_related('offer', 'from_product'):
        if not log.offer or not log.from_product:
            continue
        if log.from_product not in rejected_offers:
            rejected_offers[log.from_product] = []
        rejected_offers[log.from_product].append(
            (log.offer, log.signals.get('rejected', 'unknown'))
        )

    # Create negative pairs (from same product, different source)
    for product, rejected_list in rejected_offers.items():
        active_offers = Offer.objects.filter(product=product, last_seen_at__isnull=False)
        for offer_a in active_offers:
            for offer_b, reject_reason in rejected_list:
                if offer_a.source == offer_b.source:
                    continue

                pair = TrainingPair(
                    offer_a_name=offer_a.raw_name or offer_a.product.name,
                    offer_b_name=offer_b.raw_name or offer_b.product.name,
                    offer_a_specs=_build_offer_text(offer_a),
                    offer_b_specs=_build_offer_text(offer_b),
                    offer_a_source=offer_a.source,
                    offer_b_source=offer_b.source,
                    label=0,  # Negative: should NOT match
                    score=0.0,
                    score_confidence='high',
                    rule=reject_reason,
                    signals={'rejected': reject_reason},
                )
                pairs.append(pair)

    # Query weak pairs (REVIEW decisions - ambiguous)
    if include_weak:
        review_logs = MergeAuditLog.objects.filter(
            decision=MergeAuditLog.Decision.REVIEW,
            actor=MergeAuditLog.Actor.AUTO,
            reverted=False,
        )
        if min_date:
            review_logs = review_logs.filter(created_at__gte=min_date)

        for log in review_logs.select_related('offer'):
            if not log.offer:
                continue

            # Try to find similar offers from different sources
            offers = Offer.objects.filter(
                product=log.offer.product,
            ).exclude(source=log.offer.source)

            for other_offer in offers:
                pair = TrainingPair(
                    offer_a_name=log.offer.raw_name or log.offer.product.name,
                    offer_b_name=other_offer.raw_name or other_offer.product.name,
                    offer_a_specs=_build_offer_text(log.offer),
                    offer_b_specs=_build_offer_text(other_offer),
                    offer_a_source=log.offer.source,
                    offer_b_source=other_offer.source,
                    label=-1,  # Uncertain: borderline case
                    score=float(log.score or 0.70),
                    score_confidence='medium',
                    rule=log.signals.get('rule') if log.signals else None,
                    signals=log.signals or {},
                )
                pairs.append(pair)

    # Limit results
    if max_pairs:
        pairs = pairs[:max_pairs]

    logger.info(
        f'Exported {len(pairs)} training pairs: '
        f'{sum(1 for p in pairs if p.label == 1)} positive, '
        f'{sum(1 for p in pairs if p.label == 0)} negative, '
        f'{sum(1 for p in pairs if p.label == -1)} weak'
    )

    return pairs


def split_train_test(
    pairs: list[TrainingPair],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[list[TrainingPair], list[TrainingPair], list[TrainingPair]]:
    """
    Split pairs into train/val/test sets, stratified by label.

    Args:
        pairs: List of training pairs
        train_ratio: Fraction for training (0.8 = 80%)
        val_ratio: Fraction for validation (0.1 = 10%, rest is test)
        seed: Random seed for reproducibility

    Returns:
        (train_pairs, val_pairs, test_pairs)
    """
    import random
    random.seed(seed)

    # Group by label
    positive = [p for p in pairs if p.label == 1]
    negative = [p for p in pairs if p.label == 0]
    weak = [p for p in pairs if p.label == -1]

    # Shuffle each group
    random.shuffle(positive)
    random.shuffle(negative)
    random.shuffle(weak)

    train = []
    val = []
    test = []

    test_ratio = 1.0 - train_ratio - val_ratio

    for group in [positive, negative, weak]:
        n = len(group)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train.extend(group[:n_train])
        val.extend(group[n_train : n_train + n_val])
        test.extend(group[n_train + n_val :])

    logger.info(
        f'Split: {len(train)} train, {len(val)} val, {len(test)} test'
    )

    return train, val, test


def export_to_jsonl(pairs: list[TrainingPair], filepath: str):
    """Export pairs to JSONL format."""
    with open(filepath, 'w', encoding='utf-8') as f:
        for pair in pairs:
            f.write(json.dumps(pair.to_dict(), ensure_ascii=False) + '\n')
    logger.info(f'Exported {len(pairs)} pairs to {filepath}')


def load_from_jsonl(filepath: str) -> list[TrainingPair]:
    """Load pairs from JSONL format."""
    pairs = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            pair = TrainingPair(
                offer_a_name=data['offer_a_name'],
                offer_b_name=data['offer_b_name'],
                offer_a_specs=data['offer_a_specs'],
                offer_b_specs=data['offer_b_specs'],
                offer_a_source=data['offer_a_source'],
                offer_b_source=data['offer_b_source'],
                label=data['label'],
                score=data['score'],
                score_confidence=data['score_confidence'],
                rule=data.get('rule'),
                signals=data.get('signals'),
            )
            pairs.append(pair)
    logger.info(f'Loaded {len(pairs)} pairs from {filepath}')
    return pairs
