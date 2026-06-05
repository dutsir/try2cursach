from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _priority_score(row: dict[str, Any]) -> float:
    score = 0.0
    kind = (row.get('divergence_kind') or '').strip()
    if kind == 'disjoint_conflict':
        score += 30.0
    elif kind == 'overlap_partial':
        score += 12.0
    elif kind == 'nested_subset':
        score += 2.0

    if row.get('suspect_overmerge'):
        score += 40.0

    offers_count = int(row.get('offers_count') or 0)
    groups = row.get('groups') or []
    score += min(offers_count, 40) * 0.8
    score += len(groups) * 2.0
    disjoint_groups = sum(1 for g in groups if len(g.get('model_tokens') or []) > 0)
    score += min(disjoint_groups, 20) * 0.5
    return score


class Command(BaseCommand):
    help = (
        'Строит отдельную split/unmerge очередь из multi_offer_divergent triage '
        '(разбор over-merge кейсов вне pair-merge потока).'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--triage', required=True, help='Путь к triage JSONL.')
        parser.add_argument(
            '--output',
            default='var/dedup_split_queue.jsonl',
            help='Путь output JSONL.',
        )
        parser.add_argument(
            '--kinds',
            default='disjoint_conflict,overlap_partial',
            help='Какие divergence_kind включать (через запятую).',
        )
        parser.add_argument(
            '--only-suspect-overmerge',
            action='store_true',
            help='Оставить только suspect_overmerge=true.',
        )
        parser.add_argument(
            '--min-offers',
            type=int,
            default=0,
            help='Минимум offers_count для включения в очередь.',
        )
        parser.add_argument(
            '--category',
            default='',
            help='Опционально ограничить категорией.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Лимит строк в итоговой очереди (0 = без лимита).',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        triage_path = Path(options['triage']).resolve()
        output_path = Path(options['output']).resolve()
        kinds = {
            x.strip() for x in str(options['kinds']).split(',') if x.strip()
        }
        only_overmerge = bool(options.get('only_suspect_overmerge'))
        min_offers = max(0, int(options.get('min_offers') or 0))
        category = (options.get('category') or '').strip()
        limit = max(0, int(options.get('limit') or 0))

        rows = _load_jsonl(triage_path)
        divergent_rows = [r for r in rows if r.get('row_type') == 'multi_offer_divergent']

        queue: list[dict[str, Any]] = []
        for row in divergent_rows:
            kind = (row.get('divergence_kind') or '').strip()
            if kinds and kind not in kinds:
                continue
            if only_overmerge and not bool(row.get('suspect_overmerge')):
                continue
            if int(row.get('offers_count') or 0) < min_offers:
                continue
            if category and (row.get('category_slug') or '') != category:
                continue

            item = {
                'row_type': 'split_queue_item',
                'product_id': row.get('product_id'),
                'product_name': row.get('product_name') or '',
                'category_slug': row.get('category_slug') or '',
                'brand': row.get('brand') or '',
                'offers_count': int(row.get('offers_count') or 0),
                'divergence_kind': kind,
                'suspect_overmerge': bool(row.get('suspect_overmerge')),
                'groups_count': len(row.get('groups') or []),
                'groups': row.get('groups') or [],
                'priority_score': _priority_score(row),
                'recommended_action': 'manual_split_review',
                'status': 'pending',
                'notes': '',
            }
            queue.append(item)

        queue.sort(
            key=lambda x: (
                -float(x['priority_score']),
                -int(x['offers_count']),
                -(1 if x['suspect_overmerge'] else 0),
                str(x['category_slug']),
                int(x['product_id'] or 0),
            )
        )
        if limit > 0:
            queue = queue[:limit]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as f:
            meta = {
                'row_type': 'meta',
                'source_file': str(triage_path),
                'total_divergent_in_source': len(divergent_rows),
                'queue_size': len(queue),
                'filters': {
                    'kinds': sorted(kinds),
                    'only_suspect_overmerge': only_overmerge,
                    'min_offers': min_offers,
                    'category': category,
                    'limit': limit,
                },
            }
            f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            for item in queue:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        self.stdout.write(self.style.SUCCESS(f'Split queue сохранена: {output_path}'))
        self.stdout.write(f'Всего divergent в источнике: {len(divergent_rows)}')
        self.stdout.write(f'В очереди после фильтров: {len(queue)}')

