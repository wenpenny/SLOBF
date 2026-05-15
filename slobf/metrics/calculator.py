"""Metrics calculation for SLOBF."""

from __future__ import annotations

import math
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Compute evaluation metrics for obfuscation experiments."""

    @staticmethod
    def cosine_similarity(emb1, emb2) -> float:
        import numpy as np
        n1 = np.linalg.norm(emb1)
        n2 = np.linalg.norm(emb2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (n1 * n2))

    @staticmethod
    def topk_metrics(rank: int, k_values: list[int] = (1, 5, 10)) -> dict[str, float]:
        """Compute Top-K hit and MRR from a rank value."""
        metrics = {"rank": rank, "mrr": 1.0 / rank if rank > 0 else 0.0}
        for k in k_values:
            metrics[f"top{k}_hit"] = 1 if 1 <= rank <= k else 0
        return metrics

    @staticmethod
    def calculate_entropy(data: list | str) -> float:
        if not data:
            return 0.0
        counts = {}
        for x in data:
            counts[x] = counts.get(x, 0) + 1
        total = len(data)
        entropy = 0.0
        for c in counts.values():
            p = c / total
            entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def binary_diff_stats(orig_func: dict, obs_func: dict) -> dict[str, Any]:
        """Compare original and obfuscated binary function stats."""
        oi = orig_func.get("instruction_count", 1) or 1
        osize = orig_func.get("size", 1) or 1
        return {
            "instr_count_orig": oi,
            "instr_count_obs": obs_func.get("instruction_count", 0),
            "instr_growth_ratio": obs_func.get("instruction_count", 0) / oi,
            "size_growth_ratio": obs_func.get("size", 0) / osize,
            "bb_count_orig": orig_func.get("bb_count", 0),
            "bb_count_obs": obs_func.get("bb_count", 0),
            "opcode_entropy_orig": MetricsCalculator.calculate_entropy(
                orig_func.get("opcodes", [])
            ),
            "opcode_entropy_obs": MetricsCalculator.calculate_entropy(
                obs_func.get("opcodes", [])
            ),
        }
