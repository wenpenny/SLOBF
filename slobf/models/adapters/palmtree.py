"""PalmTree model adapter for SLOBF."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from slobf.models.base import ModelAdapter, ModelResult

logger = logging.getLogger(__name__)

class PalmTreeAdapter:
    name = "PalmTree"

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.enabled = False

    def setup(self):
        # Even without weights, we can mark as enabled for mock baseline
        self.enabled = True

    def preprocess_function(self, function_json: dict[str, Any]) -> Any:
        return {"instructions": function_json.get("instructions", [])}

    def embed(self, preprocessed_input: Any) -> ModelResult:
        """Instruction-embedding-based baseline with mean pooling."""
        if not self.enabled:
            return ModelResult(success=False, failure_reason="Model not loaded")
        
        # In real case, we'd use a BERT-like model for each instruction and pool
        mock_emb = np.random.rand(128).astype(np.float32)
        
        return ModelResult(
            success=True,
            embedding=mock_emb,
            preprocessing_metadata={"pooling": "mean_pooling"},
            deviation_notes="Instruction-embedding-based baseline (not full pipeline)"
        )

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        from slobf.models.base import ModelAdapter
        return ModelAdapter.similarity(self, emb1, emb2)
