"""Management command to fine-tune embedding model on MergeAuditLog data."""
import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from apps.products.dedupe.training_data import (
    export_merge_audit_pairs,
    export_to_jsonl,
    split_train_test,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fine-tune embedding model on MergeAuditLog training data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--epochs',
            type=int,
            default=3,
            help='Number of training epochs (default: 3)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=32,
            help='Training batch size (default: 32)',
        )
        parser.add_argument(
            '--output',
            default='./models/embedding_finetuned_v1',
            help='Output directory for trained model (default: ./models/embedding_finetuned_v1)',
        )
        parser.add_argument(
            '--max-pairs',
            type=int,
            default=None,
            help='Limit total pairs (for testing)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview data without training',
        )
        parser.add_argument(
            '--export-data-only',
            action='store_true',
            help='Only export data, do not train',
        )
        parser.add_argument(
            '--data-dir',
            default='./data/training',
            help='Directory to save training data (default: ./data/training)',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        data_dir = Path(options['data_dir'])
        data_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(self.style.HTTP_INFO('📊 Extracting training pairs from MergeAuditLog...'))

        # Export pairs
        try:
            pairs = export_merge_audit_pairs(max_pairs=options.get('max_pairs'))
        except Exception as e:
            raise CommandError(f'Failed to export training data: {e}')

        if not pairs:
            raise CommandError('No training pairs found in MergeAuditLog')

        # Print stats
        positive = sum(1 for p in pairs if p.label == 1)
        negative = sum(1 for p in pairs if p.label == 0)
        weak = sum(1 for p in pairs if p.label == -1)

        self.stdout.write(f'  ✓ Extracted {len(pairs)} pairs')
        self.stdout.write(f'    - Positive (match): {positive}')
        self.stdout.write(f'    - Negative (mismatch): {negative}')
        self.stdout.write(f'    - Weak (uncertain): {weak}')

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('\n✓ Dry-run complete (no training)\n'))
            # Print sample pairs
            self.stdout.write(self.style.HTTP_INFO('Sample pairs:'))
            for pair in pairs[:3]:
                self.stdout.write(f'\n  Pair: {pair.offer_a_source} <> {pair.offer_b_source}')
                self.stdout.write(f'    A: {pair.offer_a_name}')
                self.stdout.write(f'    B: {pair.offer_b_name}')
                self.stdout.write(f'    Label: {pair.label} ({pair.score_confidence})')
            return

        # Split data
        self.stdout.write(self.style.HTTP_INFO('\n📁 Splitting into train/val/test...'))
        train, val, test = split_train_test(pairs, train_ratio=0.8, val_ratio=0.1)

        # Export to JSONL
        try:
            export_to_jsonl(train, data_dir / 'train.jsonl')
            export_to_jsonl(val, data_dir / 'val.jsonl')
            export_to_jsonl(test, data_dir / 'test.jsonl')
            self.stdout.write(self.style.SUCCESS(f'✓ Exported to {data_dir}/'))
        except Exception as e:
            raise CommandError(f'Failed to export data: {e}')

        if options['export_data_only']:
            self.stdout.write(self.style.SUCCESS('\n✓ Data export complete\n'))
            return

        # Train model
        self.stdout.write(self.style.HTTP_INFO('\n🔧 Training embedding model...'))
        try:
            from sentence_transformers import SentenceTransformer, losses, models
            from sentence_transformers.losses import CosineSimilarityLoss
            from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator
            import torch
        except ImportError:
            raise CommandError(
                'sentence-transformers not installed. Install with: '
                'pip install sentence-transformers torch'
            )

        # Load base model
        base_model_name = getattr(
            settings,
            'DEDUP_EMBEDDING_MODEL',
            'intfloat/multilingual-e5-base',
        )
        self.stdout.write(f'  Loading base model: {base_model_name}')

        try:
            model = SentenceTransformer(base_model_name)
        except Exception as e:
            raise CommandError(f'Failed to load base model: {e}')

        # Prepare training data
        train_sentences = []
        train_labels = []
        for pair in train:
            # Only use positive and negative pairs for training (skip weak)
            if pair.label == -1:
                continue
            train_sentences.append([pair.offer_a_specs, pair.offer_b_specs])
            train_labels.append(float(pair.label))

        if not train_sentences:
            raise CommandError('No training data after filtering weak pairs')

        self.stdout.write(f'  Training on {len(train_sentences)} pairs')

        # Create loss function
        train_loss = CosineSimilarityLoss(model)

        # Prepare validation data
        val_sentences = [
            [p.offer_a_specs, p.offer_b_specs]
            for p in val
        ]
        val_labels = [
            float(p.label) if p.label != -1 else 0.5
            for p in val
        ]

        if val_sentences:
            evaluator = EmbeddingSimilarityEvaluator(
                sentences1=[s[0] for s in val_sentences],
                sentences2=[s[1] for s in val_sentences],
                scores=val_labels,
                batch_size=32,
                main_similarity=None,
                show_progress_bar=True,
            )
        else:
            evaluator = None

        # Train
        try:
            output_path = Path(options['output'])
            output_path.mkdir(parents=True, exist_ok=True)

            model.fit(
                train_objectives=[(train_sentences, train_loss)],
                evaluator=evaluator,
                epochs=options['epochs'],
                evaluation_steps=200,
                warmup_steps=100,
                output_path=str(output_path),
                save_best_model=True,
                show_progress_bar=True,
            )

            self.stdout.write(self.style.SUCCESS(f'\n✓ Model trained and saved to {output_path}/'))

            # Save metadata
            metadata = {
                'base_model': base_model_name,
                'training_pairs': len(train_sentences),
                'validation_pairs': len(val_sentences),
                'test_pairs': len(test),
                'epochs': options['epochs'],
                'batch_size': options['batch_size'],
                'embedding_dim': model.get_sentence_embedding_dimension(),
            }
            with open(output_path / 'metadata.json', 'w') as f:
                json.dump(metadata, f, indent=2)

            self.stdout.write(self.style.SUCCESS('\n✓ Training complete! 🎉'))
            self.stdout.write(
                f'\nNext steps:'
                f'\n  1. Review model metrics'
                f'\n  2. Run: python manage.py rebuild_embeddings --model {output_path}'
                f'\n  3. Monitor MergeAuditLog in shadow mode'
            )

        except Exception as e:
            raise CommandError(f'Training failed: {e}')
