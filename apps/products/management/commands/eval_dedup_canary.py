from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser


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


def _normalize_verdict(value: Any) -> str:
    return str(value or '').strip().lower()


def _wilson_interval(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + (z * z) / (4 * n)) / n) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return low, high


class Command(BaseCommand):
    help = (
        'Считает live false-merge rate по размеченному canary-файлу '
        '(manual_verdict из dedup_auto_canary).'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--input', required=True, help='Путь к canary JSONL/CSV.')
        parser.add_argument(
            '--max-fmr',
            type=float,
            default=0.02,
            help='Порог предупреждения для false-merge-rate (по умолчанию 0.02).',
        )
        parser.add_argument(
            '--output',
            default='',
            help='Опционально: путь для JSON-отчёта.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options['input']).resolve()
        threshold = float(options['max_fmr'])
        output = (options.get('output') or '').strip()

        rows = _load_rows(path)
        data_rows = [r for r in rows if r.get('row_type') != 'meta']
        reviewed = [
            r for r in data_rows
            if _normalize_verdict(r.get('manual_verdict')) in {'correct_merge', 'wrong_merge'}
        ]
        unreviewed = len(data_rows) - len(reviewed)

        wrong = sum(
            1 for r in reviewed
            if _normalize_verdict(r.get('manual_verdict')) == 'wrong_merge'
        )
        correct = sum(
            1 for r in reviewed
            if _normalize_verdict(r.get('manual_verdict')) == 'correct_merge'
        )
        n = len(reviewed)
        fmr = (wrong / n) if n else 0.0
        precision = (correct / n) if n else 0.0
        low, high = _wilson_interval(fmr, n)

        def bucket_stats(key: str) -> dict[str, dict[str, float | int]]:
            buckets: dict[str, dict[str, int]] = {}
            for row in reviewed:
                name = str(row.get(key) or 'unknown').strip() or 'unknown'
                b = buckets.setdefault(name, {'n': 0, 'wrong': 0, 'correct': 0})
                b['n'] += 1
                v = _normalize_verdict(row.get('manual_verdict'))
                if v == 'wrong_merge':
                    b['wrong'] += 1
                elif v == 'correct_merge':
                    b['correct'] += 1
            out: dict[str, dict[str, float | int]] = {}
            for name, b in sorted(buckets.items(), key=lambda kv: (-kv[1]['n'], kv[0])):
                nn = b['n']
                rr = (b['wrong'] / nn) if nn else 0.0
                pp = (b['correct'] / nn) if nn else 0.0
                l, h = _wilson_interval(rr, nn)
                out[name] = {
                    'reviewed': nn,
                    'wrong_merge': b['wrong'],
                    'correct_merge': b['correct'],
                    'false_merge_rate': rr,
                    'precision': pp,
                    'fmr_ci_low': l,
                    'fmr_ci_high': h,
                }
            return out

        by_source = bucket_stats('offer_source')
        by_category = bucket_stats('to_product_category')
        by_run = bucket_stats('run_id')

        report = {
            'input': str(path),
            'rows_total': len(data_rows),
            'reviewed': n,
            'unreviewed': unreviewed,
            'wrong_merge': wrong,
            'correct_merge': correct,
            'false_merge_rate': fmr,
            'precision': precision,
            'fmr_ci_low': low,
            'fmr_ci_high': high,
            'threshold': threshold,
            'alert': (n > 0 and fmr > threshold),
            'by_source': by_source,
            'by_category': by_category,
            'by_run_id': by_run,
        }

        self.stdout.write('=== Dedup Canary Eval ===')
        self.stdout.write(f"Rows total: {report['rows_total']}")
        self.stdout.write(f"Reviewed: {report['reviewed']} | Unreviewed: {report['unreviewed']}")
        self.stdout.write(
            f"False-merge-rate: {report['false_merge_rate']:.4f} "
            f"(95% CI {report['fmr_ci_low']:.4f}..{report['fmr_ci_high']:.4f})"
        )
        self.stdout.write(f"Precision: {report['precision']:.4f}")
        if report['alert']:
            self.stdout.write(self.style.WARNING(f"ALERT: FMR > {threshold:.4f}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"OK: FMR <= {threshold:.4f}"))

        self.stdout.write('Top by source:')
        for source, vals in list(report['by_source'].items())[:8]:
            self.stdout.write(
                f"  {source}: n={vals['reviewed']} "
                f"fmr={vals['false_merge_rate']:.4f} "
                f"ci={vals['fmr_ci_low']:.4f}..{vals['fmr_ci_high']:.4f}"
            )

        if output:
            out_path = Path(output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open('w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f'JSON-отчёт сохранён: {out_path}'))

