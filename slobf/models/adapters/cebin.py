"""CEBin model adapter for SLOBF."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from slobf.models.base import ModelAdapter, ModelResult

logger = logging.getLogger(__name__)

class CEBinAdapter:
    name = "CEBin"

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.enabled = False
        self.commit_hash = "official_v1.0" # Example

    def setup(self):
        """Setup CEBin environment and load weights."""
        if not self.model_path:
            logger.warning("CEBin model path not provided. Model will be disabled.")
            return
        
        # In a real setup, we would load the model here
        # self.model = load_cebin(self.model_path)
        self.enabled = True
        logger.info("CEBin adapter initialized.")

    def preprocess_function(self, function_json: dict[str, Any]) -> Any:
        """Preprocessing based on CEBin's requirements (Control Flow Graph + Features)."""
        # CEBin often uses a normalized CFG. 
        # Since we use Capstone, we provide basic blocks and features.
        return {
            "opcodes": function_json.get("opcodes", []),
            "bb_count": function_json.get("bb_count", 0),
            "mode": "open_source_compatible"
        }

    def embed(self, preprocessed_input: Any) -> ModelResult:
        if not self.enabled:
            return ModelResult(success=False, failure_reason="Model not loaded")
        
        # Mocking embedding for now
        # In real case: emb = self.model.predict(preprocessed_input)
        mock_emb = np.random.rand(128).astype(np.float32)
        
        return ModelResult(
            success=True,
            embedding=mock_emb,
            model_version=self.commit_hash,
            preprocessing_backend="open_source_compatible"
        )

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        from slobf.models.base import ModelAdapter
        return ModelAdapter.similarity(self, emb1, emb2)
