"""Model registry and versioning for embedding models."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for tracking embedding model versions and metrics."""

    def __init__(self, registry_file: str = './models/registry.json'):
        """
        Initialize registry.

        Args:
            registry_file: Path to registry JSON file
        """
        self.registry_file = Path(registry_file)
        self._models: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        """Load registry from file."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    self._models = json.load(f)
                logger.info(f'Loaded registry with {len(self._models)} models')
            except Exception as e:
                logger.warning(f'Failed to load registry: {e}')
                self._models = {}
        else:
            self._models = {}

    def save(self):
        """Save registry to file."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_file, 'w') as f:
            json.dump(self._models, f, indent=2, default=str)
        logger.info(f'Saved registry to {self.registry_file}')

    def register(
        self,
        model_id: str,
        model_name: str,
        source: str,  # 'huggingface' or 'local'
        path: Optional[str] = None,
        embedding_dim: int = 768,
        training_data: Optional[str] = None,
        metrics: Optional[Dict[str, float]] = None,
    ):
        """
        Register a model.

        Args:
            model_id: Unique identifier (e.g., 'embedding_v1_finetuned')
            model_name: Human-readable name
            source: Source ('huggingface' or 'local')
            path: Path to model if local
            embedding_dim: Embedding dimension
            training_data: Description of training data used
            metrics: Dict of metrics (f1, precision, recall, etc.)
        """
        self._models[model_id] = {
            'model_id': model_id,
            'model_name': model_name,
            'source': source,
            'path': path,
            'embedding_dim': embedding_dim,
            'training_data': training_data,
            'metrics': metrics or {},
            'created_at': datetime.utcnow().isoformat(),
        }
        self.save()
        logger.info(f'Registered model: {model_id}')

    def get(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model info by ID."""
        return self._models.get(model_id)

    def list(self) -> list[Dict[str, Any]]:
        """List all registered models."""
        return list(self._models.values())

    def get_latest_local(self) -> Optional[Dict[str, Any]]:
        """Get the most recently created local model."""
        local_models = [
            m for m in self._models.values()
            if m['source'] == 'local'
        ]
        if not local_models:
            return None
        return sorted(
            local_models,
            key=lambda m: m['created_at'],
            reverse=True
        )[0]

    def get_best_by_metric(
        self,
        metric_name: str,
        source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get model with best metric value."""
        models = [
            m for m in self._models.values()
            if source is None or m['source'] == source
        ]

        best = None
        best_value = -1.0

        for model in models:
            value = model['metrics'].get(metric_name, -1.0)
            if value > best_value:
                best = model
                best_value = value

        return best

    def set_metrics(self, model_id: str, metrics: Dict[str, float]):
        """Update metrics for a model."""
        if model_id in self._models:
            self._models[model_id]['metrics'].update(metrics)
            self.save()
            logger.info(f'Updated metrics for {model_id}')

    def delete(self, model_id: str):
        """Remove model from registry."""
        if model_id in self._models:
            del self._models[model_id]
            self.save()
            logger.info(f'Removed model: {model_id}')


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    """Get or create global registry."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def register_model(**kwargs):
    """Convenience function to register a model."""
    get_registry().register(**kwargs)


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get model info."""
    return get_registry().get(model_id)


def list_models() -> list[Dict[str, Any]]:
    """Convenience function to list all models."""
    return get_registry().list()
