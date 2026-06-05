from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser


@dataclass
class PairRow:
    pair_key: str
    category_slug: str
    product_a_id: int | None
    product_b_id: int | None
    product_a_name: str
    product_b_name: str
    score: float
    signals: dict[str, Any]
    generators: set[str] = field(default_factory=set)
    passes: set[str] = field(default_factory=set)
    row_types: set[str] = field(default_factory=set)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _primary_provenance(rec: PairRow) -> str:
    if 'category_mpn_exact' in rec.passes:
        return 'category_mpn_exact'
    if 'category_model_tokens' in rec.passes:
        return 'category_model_tokens'
    if 'category_brand_name_trigram' in rec.passes:
        return 'category_brand_name_trigram'
    if 'pending_review_queue' in rec.generators:
        return 'pending_review_queue'
    if rec.generators:
        return sorted(rec.generators)[0]
    return 'unknown'


def _score_band(score: float, *, threshold: float, near_delta: float) -> str:
    if abs(score - threshold) <= near_delta:
        return 'near_threshold'
    if score > threshold + near_delta:
        return 'high_score'
    return 'low_score'


def _sample_stratified(
    rows: list[PairRow],
    *,
    target: int,
    rng: random.Random,
) -> list[PairRow]:
    if target <= 0 or not rows:
        return []

    by_stratum: dict[tuple[str, str], list[PairRow]] = defaultdict(list)
    for row in rows:
        by_stratum[(row.category_slug or 'unknown', _primary_provenance(row))].append(row)
    for bucket in by_stratum.values():
        rng.shuffle(bucket)

    selected: list[PairRow] = []
    # 1) Минимум по 1 из каждой страты.
    strata_keys = list(by_stratum.keys())
    rng.shuffle(strata_keys)
    for key in strata_keys:
        if len(selected) >= target:
            break
        bucket = by_stratum[key]
        if bucket:
            selected.append(bucket.pop())

    # 2) Добиваем пропорционально остатком.
    remaining_pool: list[PairRow] = []
    for bucket in by_stratum.values():
        remaining_pool.extend(bucket)
    if len(selected) < target and remaining_pool:
        need = min(target - len(selected), len(remaining_pool))
        selected.extend(rng.sample(remaining_pool, need))
    return selected


class Command(BaseCommand):
    help = (
        'Строит стратифицированный golden-сэмпл из triage JSONL '
        '(после запуска export_dedup_triage).'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--triage', required=True, help='Путь к triage JSONL.')
        parser.add_argument('--output', default='var/golden_sample.jsonl', help='Куда сохранить golden sample.')
        parser.add_argument('--size', type=int, default=800, help='Размер golden-сэмпла.')
        parser.add_argument('--seed', type=int, default=42, help='Seed для воспроизводимости.')
        parser.add_argument('--threshold', type=float, default=0.80, help='Рабочий порог score.')
        parser.add_argument(
            '--near-delta',
            type=float,
            default=0.07,
            help='Полуширина near-threshold зоны (|score-threshold| <= near_delta).',
        )
        parser.add_argument(
            '--near-ratio',
            type=float,
            default=0.60,
            help='Доля near-threshold пар в выборке.',
        )
        parser.add_argument(
            '--high-ratio',
            type=float,
            default=0.20,
            help='Доля high-score пар в выборке.',
        )
        parser.add_argument(
            '--low-ratio',
            type=float,
            default=0.20,
            help='Доля low-score пар в выборке.',
        )
        parser.add_argument('--category', default='', help='Опционально ограничить категорией.')

    def handle(self, *args: Any, **options: Any) -> None:
        triage_path = Path(options['triage']).resolve()
        output_path = Path(options['output']).resolve()
        size = max(1, int(options['size']))
        seed = int(options['seed'])
        threshold = float(options['threshold'])
        near_delta = float(options['near_delta'])
        near_ratio = float(options['near_ratio'])
        high_ratio = float(options['high_ratio'])
        low_ratio = float(options['low_ratio'])
        category_filter = (options.get('category') or '').strip()
        rng = random.Random(seed)

        rows = _load_jsonl(triage_path)
        pair_map: dict[str, PairRow] = {}
        for row in rows:
            if row.get('row_type') == 'meta':
                continue
            pair_key = (row.get('pair_key') or '').strip()
            if not pair_key:
                continue
            category_slug = (row.get('category_slug') or '').strip()
            if category_filter and category_slug != category_filter:
                continue

            score = _safe_float(row.get('signature_dice'), 0.0)
            rec = pair_map.get(pair_key)
            if rec is None:
                rec = PairRow(
                    pair_key=pair_key,
                    category_slug=category_slug,
                    product_a_id=row.get('product_a_id'),
                    product_b_id=row.get('product_b_id'),
                    product_a_name=(row.get('product_a_name') or ''),
                    product_b_name=(row.get('product_b_name') or ''),
                    score=score,
                    signals=row.get('signals') or {},
                )
                pair_map[pair_key] = rec
            else:
                if score > rec.score:
                    rec.score = score
                    rec.signals = row.get('signals') or rec.signals
                    rec.product_a_name = (row.get('product_a_name') or rec.product_a_name)
                    rec.product_b_name = (row.get('product_b_name') or rec.product_b_name)
            rec.row_types.add((row.get('row_type') or 'unknown'))
            prov = row.get('provenance') or {}
            gen = (prov.get('generator') or '').strip()
            if gen:
                rec.generators.add(gen)
            for p in (prov.get('passes') or []):
                if p:
                    rec.passes.add(str(p))

        all_pairs = list(pair_map.values())
        if not all_pairs:
            self.stdout.write(self.style.WARNING('В triage нет pair-строк для выборки.'))
            return

        near_target = int(round(size * near_ratio))
        high_target = int(round(size * high_ratio))
        low_target = max(0, size - near_target - high_target)

        by_band: dict[str, list[PairRow]] = defaultdict(list)
        for rec in all_pairs:
            band = _score_band(rec.score, threshold=threshold, near_delta=near_delta)
            by_band[band].append(rec)

        selected: list[PairRow] = []
        selected.extend(
            _sample_stratified(by_band.get('near_threshold', []), target=near_target, rng=rng)
        )
        selected.extend(
            _sample_stratified(by_band.get('high_score', []), target=high_target, rng=rng)
        )
        selected.extend(
            _sample_stratified(by_band.get('low_score', []), target=low_target, rng=rng)
        )

        # Добираем до size из остатка, если какой-то band не хватило.
        selected_keys = {x.pair_key for x in selected}
        remain = [x for x in all_pairs if x.pair_key not in selected_keys]
        if len(selected) < size and remain:
            selected.extend(rng.sample(remain, min(size - len(selected), len(remain))))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as f:
            meta = {
                'row_type': 'meta',
                'sample_size': len(selected),
                'source_pairs_total': len(all_pairs),
                'threshold': threshold,
                'near_delta': near_delta,
                'seed': seed,
                'ratios': {
                    'near_ratio': near_ratio,
                    'high_ratio': high_ratio,
                    'low_ratio': low_ratio,
                },
                'category_filter': category_filter,
            }
            f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            for rec in selected:
                row = {
                    'pair_key': rec.pair_key,
                    'category_slug': rec.category_slug,
                    'product_a_id': rec.product_a_id,
                    'product_b_id': rec.product_b_id,
                    'product_a_name': rec.product_a_name,
                    'product_b_name': rec.product_b_name,
                    'score': rec.score,
                    'score_band': _score_band(rec.score, threshold=threshold, near_delta=near_delta),
                    'row_types': sorted(rec.row_types),
                    'provenance_generators': sorted(rec.generators),
                    'provenance_passes': sorted(rec.passes),
                    'primary_provenance': _primary_provenance(rec),
                    'signals': rec.signals,
                    'label': None,
                    'notes': '',
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')

        self.stdout.write(self.style.SUCCESS(f'Golden sample сохранён: {output_path}'))
        self.stdout.write(f'Всего уникальных пар в triage: {len(all_pairs)}')
        self.stdout.write(f'В выборке: {len(selected)}')

