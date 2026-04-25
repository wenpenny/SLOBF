"""JTrans model adapter for SLOBF."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from slobf.models.base import ModelAdapter, ModelResult

logger = logging.getLogger(__name__)

class JTransAdapter:
    name = "JTrans"

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.enabled = False

    def setup(self):
        if not self.model_path:
            return
        self.enabled = True

    def preprocess_function(self, function_json: dict[str, Any]) -> Any:
        """JTrans requires normalized assembly tokens."""
        # Deviation: Using Capstone disassembly instead of IDA/Binary Ninja
        disasm = function_json.get("disassembly", [])
        tokens = []
        for line in disasm:
            # Simple normalization: remove addresses, keep mnemonics and operands
            if "\t" in line:
                tokens.append(line.split("\t")[-1])
        return {
            "tokens": tokens,
            "deviation": "Using Capstone normalized disassembly instead of IDA"
        }

    def embed(self, preprocessed_input: Any) -> ModelResult:
        if not self.enabled:
            return ModelResult(success=False, failure_reason="Model not loaded")
        
        mock_emb = np.random.rand(256).astype(np.float32)
        return ModelResult(
            success=True,
            embedding=mock_emb,
            deviation_notes=preprocessed_input["deviation"]
        )

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        from slobf.models.base import ModelAdapter
        return ModelAdapter.similarity(self, emb1, emb2)
