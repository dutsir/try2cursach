from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == '.csv':
        with path.open('r', encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _parse_label(raw: Any, positive_labels: set[str], negative_labels: set[str]) -> bool | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    if text in positive_labels:
        return True
    if text in negative_labels:
        return False
    return None


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


class Command(BaseCommand):
    help = (
        'Оценивает golden-set: отдельно recall блокинга и качество скорера '
        '(precision/recall/F1/false-merge-rate) на блокированных парах.'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--golden', required=True, help='Путь к размеченному golden (JSONL/CSV).')
        parser.add_argument('--candidates', required=True, help='Путь к triage/candidates JSONL.')
        parser.add_argument(
            '--score-threshold',
            type=float,
            default=0.80,
            help='Порог score-предикта merge (по умолчанию 0.80).',
        )
        parser.add_argument(
            '--score-field',
            default='signature_dice',
            help='Поле score в candidates (по умолчанию signature_dice).',
        )
        parser.add_argument(
            '--output',
            default='',
            help='Опционально: путь для JSON-отчёта с метриками.',
        )
        parser.add_argument(
            '--positive-labels',
            default='1,match,merge,yes,true',
            help='Список положительных меток через запятую.',
        )
        parser.add_argument(
            '--negative-labels',
            default='0,nomatch,no_merge,no,false',
            help='Список отрицательных меток через запятую.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        golden_path = Path(options['golden']).resolve()
        candidates_path = Path(options['candidates']).resolve()
        threshold = float(options['score_threshold'])
        score_field = str(options['score_field']).strip()
        output = (options.get('output') or '').strip()

        pos_labels = {x.strip().lower() for x in str(options['positive_labels']).split(',') if x.strip()}
        neg_labels = {x.strip().lower() for x in str(options['negative_labels']).split(',') if x.strip()}

        golden_rows = _load_rows(golden_path)
        candidate_rows = _load_rows(candidates_path)

        meta = next((r for r in candidate_rows if r.get('row_type') == 'meta'), {})
        candidate_map: dict[str, dict[str, Any]] = {}
        for row in candidate_rows:
            if row.get('row_type') == 'meta':
                continue
            key = (row.get('pair_key') or '').strip()
            if not key:
                continue
            prev = candidate_map.get(key)
            if prev is None or _safe_float(row.get(score_field), 0.0) > _safe_float(prev.get(score_field), 0.0):
                candidate_map[key] = row

        labeled: list[dict[str, Any]] = []
        for row in golden_rows:
            key = (row.get('pair_key') or '').strip()
            if not key:
                continue
            label = _parse_label(row.get('label'), pos_labels, neg_labels)
            if label is None:
                continue
            cand = candidate_map.get(key)
            blocked = cand is not None
            score = _safe_float((cand or {}).get(score_field), 0.0)
            labeled.append({
                'pair_key': key,
                'category_slug': (row.get('category_slug') or (cand or {}).get('category_slug') or '').strip(),
                'label': label,
                'blocked': blocked,
                'score': score,
                'pred_merge': blocked and (score >= threshold),
            })

        if not labeled:
            self.stdout.write(self.style.WARNING('Нет размеченных golden-строк (label пустой/непонятный).'))
            return

        positives_total = sum(1 for x in labeled if x['label'])
        positives_blocked = sum(1 for x in labeled if x['label'] and x['blocked'])
        blocking_recall = (positives_blocked / positives_total) if positives_total else 0.0

        blocked_rows = [x for x in labeled if x['blocked']]
        tp = sum(1 for x in blocked_rows if x['pred_merge'] and x['label'])
        fp = sum(1 for x in blocked_rows if x['pred_merge'] and not x['label'])
        fn = sum(1 for x in blocked_rows if (not x['pred_merge']) and x['label'])
        tn = sum(1 for x in blocked_rows if (not x['pred_merge']) and (not x['label']))

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = _f1(precision, recall)
        false_merge_rate = fp / (tp + fp) if (tp + fp) else 0.0

        by_cat: dict[str, dict[str, int]] = {}
        for row in labeled:
            cat = row['category_slug'] or 'unknown'
            bucket = by_cat.setdefault(cat, {
                'golden_total': 0, 'golden_pos': 0, 'golden_pos_blocked': 0,
                'blocked_total': 0, 'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0,
            })
            bucket['golden_total'] += 1
            if row['label']:
                bucket['golden_pos'] += 1
                if row['blocked']:
                    bucket['golden_pos_blocked'] += 1
            if row['blocked']:
                bucket['blocked_total'] += 1
                if row['pred_merge'] and row['label']:
                    bucket['tp'] += 1
                elif row['pred_merge'] and (not row['label']):
                    bucket['fp'] += 1
                elif (not row['pred_merge']) and row['label']:
                    bucket['fn'] += 1
                else:
                    bucket['tn'] += 1

        by_cat_report: dict[str, dict[str, float | int]] = {}
        for cat, b in sorted(by_cat.items()):
            cat_precision = b['tp'] / (b['tp'] + b['fp']) if (b['tp'] + b['fp']) else 0.0
            cat_recall = b['tp'] / (b['tp'] + b['fn']) if (b['tp'] + b['fn']) else 0.0
            by_cat_report[cat] = {
                'golden_total': b['golden_total'],
                'blocking_recall': (
                    b['golden_pos_blocked'] / b['golden_pos'] if b['golden_pos'] else 0.0
                ),
                'precision': cat_precision,
                'recall': cat_recall,
                'f1': _f1(cat_precision, cat_recall),
                'false_merge_rate': (
                    b['fp'] / (b['tp'] + b['fp']) if (b['tp'] + b['fp']) else 0.0
                ),
            }

        report = {
            'golden_rows_labeled': len(labeled),
            'score_field': score_field,
            'score_threshold': threshold,
            'blocking': {
                'positives_total': positives_total,
                'positives_blocked': positives_blocked,
                'recall': blocking_recall,
                'pair_reduction_ratio': _safe_float(meta.get('pair_reduction_ratio'), 0.0),
                'all_possible_pairs': int(meta.get('all_possible_pairs') or 0),
                'blocking_pairs': int(meta.get('blocking_v2_pairs') or 0),
            },
            'scorer_on_blocked_pairs': {
                'blocked_rows': len(blocked_rows),
                'tp': tp,
                'fp': fp,
                'fn': fn,
                'tn': tn,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'false_merge_rate': false_merge_rate,
            },
            'by_category': by_cat_report,
        }

        self.stdout.write('=== Dedup Eval ===')
        self.stdout.write(f"Labeled golden rows: {report['golden_rows_labeled']}")
        self.stdout.write(
            f"Blocking recall: {report['blocking']['recall']:.4f} "
            f"({report['blocking']['positives_blocked']}/{report['blocking']['positives_total']})"
        )
        self.stdout.write(
            f"Pair reduction ratio: {report['blocking']['pair_reduction_ratio']:.4f} "
            f"({report['blocking']['blocking_pairs']}/{report['blocking']['all_possible_pairs']})"
        )
        scorer = report['scorer_on_blocked_pairs']
        self.stdout.write(
            f"Scorer precision={scorer['precision']:.4f} recall={scorer['recall']:.4f} "
            f"f1={scorer['f1']:.4f} false_merge_rate={scorer['false_merge_rate']:.4f}"
        )
        self.stdout.write('By category:')
        for cat, vals in report['by_category'].items():
            self.stdout.write(
                f"  {cat}: block_recall={vals['blocking_recall']:.4f} "
                f"P={vals['precision']:.4f} R={vals['recall']:.4f} "
                f"F1={vals['f1']:.4f} FMR={vals['false_merge_rate']:.4f}"
            )

        if output:
            out_path = Path(output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open('w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f'JSON-отчёт сохранён: {out_path}'))

