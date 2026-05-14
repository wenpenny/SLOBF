"""CLAP model adapter for SLOBF."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from slobf.models.base import ModelAdapter, ModelResult

logger = logging.getLogger(__name__)

class CLAPAdapter:
    name = "CLAP"

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.enabled = False

    def setup(self):
        # CLAP stability check
        if not self.model_path:
            logger.info("CLAP disabled (no model path)")
            return
        # If unstable, keep disabled
        self.enabled = False 

    def preprocess_function(self, function_json: dict[str, Any]) -> Any:
        return {}

    def embed(self, preprocessed_input: Any) -> ModelResult:
        return ModelResult(success=False, failure_reason="CLAP currently disabled for stability")

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        from slobf.models.base import ModelAdapter
        return ModelAdapter.similarity(self, emb1, emb2)
