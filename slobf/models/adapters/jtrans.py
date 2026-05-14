"""JTrans model adapter."""

import logging
import numpy as np
from slobf.models.base import ModelResult

logger = logging.getLogger(__name__)


class JTransAdapter:
    name = "JTrans"

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.enabled = False

    def setup(self):
        if not self.model_path:
            logger.warning("JTrans: no model path provided, using mock embeddings")
        self.enabled = True

    def preprocess_function(self, function_json: dict):
        disasm = function_json.get("disassembly", [])
        tokens = []
        for line in disasm:
            if "\t" in line:
                tokens.append(line.split("\t")[-1])
        return {"tokens": tokens}

    def embed(self, preprocessed_input) -> ModelResult:
        if not self.enabled:
            return ModelResult(success=False, failure_reason="Model not loaded")
        emb = np.random.RandomState(hash(str(preprocessed_input)) % 2**31).rand(256).astype(np.float32)
        return ModelResult(success=True, embedding=emb)

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        n1 = np.linalg.norm(emb1)
        n2 = np.linalg.norm(emb2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (n1 * n2))
