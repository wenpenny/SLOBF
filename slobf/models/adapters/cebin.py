"""CEBin model adapter."""

import logging
import numpy as np
from slobf.models.base import ModelResult

logger = logging.getLogger(__name__)


class CEBinAdapter:
    name = "CEBin"

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.enabled = False
        self.commit_hash = "official_v1.0"

    def setup(self):
        if not self.model_path:
            logger.warning("CEBin: no model path provided, using mock embeddings")
        self.enabled = True

    def preprocess_function(self, function_json: dict):
        return {
            "opcodes": function_json.get("opcodes", []),
            "bb_count": function_json.get("bb_count", 0),
        }

    def embed(self, preprocessed_input) -> ModelResult:
        if not self.enabled:
            return ModelResult(success=False, failure_reason="Model not loaded")
        # TODO: replace with real CEBin inference
        emb = np.random.RandomState(hash(str(preprocessed_input)) % 2**31).rand(128).astype(np.float32)
        return ModelResult(success=True, embedding=emb, model_version=self.commit_hash)

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        n1 = np.linalg.norm(emb1)
        n2 = np.linalg.norm(emb2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (n1 * n2))
