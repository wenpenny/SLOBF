"""Base class and data structures for model adapters in SLOBF."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np


@dataclass
class ModelResult:
    success: bool
    embedding: np.ndarray | None = None
    preprocessing_metadata: dict[str, Any] = field(default_factory=dict)
    failure_reason: str | None = None
    runtime: float = 0.0
    model_version: str = "unknown"
    preprocessing_backend: str = "open_source_compatible"
    deviation_notes: str | None = None


@runtime_checkable
class ModelAdapter(Protocol):
    name: str

    def setup(self) -> None:
        """Load model weights and initialize resources."""
        ...

    def preprocess_function(self, function_json: dict[str, Any]) -> Any:
        """Convert SLOBF function JSON to model-specific input."""
        ...

    def embed(self, preprocessed_input: Any) -> ModelResult:
        """Generate embedding for a single preprocessed input."""
        ...

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))

    def batch_embed(self, function_json_list: list[dict[str, Any]]) -> list[ModelResult]:
        """Generate embeddings for a list of functions."""
        results = []
        for func in function_json_list:
            start_time = time.time()
            try:
                pre_input = self.preprocess_function(func)
                res = self.embed(pre_input)
                res.runtime = time.time() - start_time
                results.append(res)
            except Exception as e:
                results.append(ModelResult(
                    success=False,
                    failure_reason=str(e),
                    runtime=time.time() - start_time
                ))
        return results
