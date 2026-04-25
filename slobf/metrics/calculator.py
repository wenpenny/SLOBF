"""Metrics calculation for SLOBF."""

import json
import logging
import math
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

class MetricsCalculator:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir

    def calculate_entropy(self, data: str | list) -> float:
        """Calculate Shannon entropy of a sequence."""
        if not data:
            return 0.0
        
        counts = {}
        for x in data:
            counts[x] = counts.get(x, 0) + 1
        
        entropy = 0.0
        length = len(data)
        for count in counts.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    def run_check(self):
        """Perform 'True Obfuscation' check by comparing original and obfuscated functions."""
        extraction_csv = self.results_dir / "extraction_results.csv"
        if not extraction_csv.exists():
            logger.error("Extraction results not found")
            return

        df = pd.read_csv(extraction_csv)
        
        # Load obfuscation summary to get source hashes
        obs_summary = pd.read_csv(self.results_dir / "obfuscation_summary.csv")
        
        results = []
        
        # Group by function and optimization level
        for (func_id, opt), group in df.groupby(["function_id", "opt"]):
            # Get original
            orig_row = group[group["operator"].isna()]
            if orig_row.empty:
                continue
            
            with open(orig_row.iloc[0]["json_path"]) as f:
                orig_data = json.load(f)

            # Get obfuscated versions
            for _, obs_row in group[group["operator"].notna()].iterrows():
                with open(obs_row["json_path"]) as f:
                    obs_data = json.load(f)
                
                # Binary change check
                binary_changed = (orig_data["instruction_hash"] != obs_data["instruction_hash"]) or \
                                 (orig_data["opcode_hash"] != obs_data["opcode_hash"])
                
                # Metrics
                results.append({
                    "function_id": func_id,
                    "opt": opt,
                    "operator": obs_row["operator"],
                    "seed": obs_row["seed"],
                    "binary_changed": binary_changed,
                    "instr_count_growth": obs_data["instruction_count"] / orig_data["instruction_count"] if orig_data["instruction_count"] > 0 else 0,
                    "size_growth": obs_data["size"] / orig_data["size"] if orig_data["size"] > 0 else 0,
                    "opcode_entropy_orig": self.calculate_entropy(orig_data["opcodes"]),
                    "opcode_entropy_obs": self.calculate_entropy(obs_data["opcodes"]),
                    "bb_count_orig": orig_data["bb_count"],
                    "bb_count_obs": obs_data["bb_count"],
                })

        pd.DataFrame(results).to_csv(self.results_dir / "true_obfuscation_check.csv", index=False)
        logger.info("True obfuscation check complete.")
