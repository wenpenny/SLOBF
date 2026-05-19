"""CLAP model adapter — HuggingFace hustcw/clap-asm.

Input:  assembly text (newline-separated disassembly lines)
Output: embedding vector via mean-pooled last_hidden_state
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import torch
from slobf.models.base import ModelResult

logger = logging.getLogger(__name__)


class CLAPAdapter:
    name = "CLAP"

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path  # not used; loads from HuggingFace
        self.enabled = False
        self._device = None
        self._tokenizer = None
        self._encoder = None

    def setup(self):
        from transformers import AutoModel, AutoTokenizer

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("CLAP: loading hustcw/clap-asm on %s", self._device)

        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                "hustcw/clap-asm", trust_remote_code=True, local_files_only=True
            )
            self._encoder = AutoModel.from_pretrained(
                "hustcw/clap-asm", trust_remote_code=True, local_files_only=True
            )
        except (OSError, ValueError):
            logger.info("CLAP: not found locally, downloading from HuggingFace...")
            self._tokenizer = AutoTokenizer.from_pretrained(
                "hustcw/clap-asm", trust_remote_code=True, local_files_only=False
            )
            self._encoder = AutoModel.from_pretrained(
                "hustcw/clap-asm", trust_remote_code=True, local_files_only=False
            )
        self._encoder.to(self._device)
        self._encoder.eval()
        self.enabled = True
        logger.info("CLAP: ready")

    def preprocess_function(self, function_json: dict[str, Any]) -> Any:
        disasm = function_json.get("disassembly", [])
        # CLAP expects {"1": "mov edx, 6", "2": "xor eax, eax", ...}
        # Strip capstone address prefix and number instructions from 1
        import json
        instructions = {}
        for i, line in enumerate(disasm, start=1):
            if "\t" in line:
                _, ins = line.split("\t", 1)
            else:
                ins = line
            instructions[str(i)] = ins.strip()
        asm_json = json.dumps(instructions)
        return {"asm_text": asm_json}

    def embed(self, preprocessed_input: Any) -> ModelResult:
        if not self.enabled:
            return ModelResult(success=False, failure_reason="CLAP not loaded")
        try:
            import json
            asm_text = preprocessed_input.get("asm_text", "")
            asm_dict = json.loads(asm_text)
            # Tokenizer expects a list of dicts: [{"1": "endbr64", ...}]
            inputs = self._tokenizer(
                [asm_dict], padding=True, return_tensors="pt"
            ).to(self._device)
            with torch.no_grad():
                output = self._encoder(**inputs)
            # CLAP encoder returns (batch, dim) pooled embedding directly
            if hasattr(output, "last_hidden_state"):
                emb = output.last_hidden_state.mean(dim=1)
            elif isinstance(output, torch.Tensor):
                emb = output
            else:
                emb = output[0]
            emb_np = emb.squeeze(0).cpu().numpy()
            return ModelResult(success=True, embedding=emb_np.astype(np.float32))
        except Exception as e:
            return ModelResult(success=False, failure_reason=str(e))

    def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        n1 = np.linalg.norm(emb1)
        n2 = np.linalg.norm(emb2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (n1 * n2))
