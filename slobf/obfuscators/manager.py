"""Manager for applying obfuscation operators in SLOBF."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from tree_sitter import Node

from slobf.config import SlobfConfig
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.obfuscators.opi import OPIObfuscator
from slobf.obfuscators.cff import CFFObfuscator
from slobf.obfuscators.er import ERObfuscator
from slobf.obfuscators.de import DEObfuscator
from slobf.obfuscators.jci import JCIObfuscator
from slobf.obfuscators.fs import FSObfuscator
from slobf.parser.c_parser import CParser

logger = logging.getLogger(__name__)

class ObfuscationManager:
    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.parser = CParser()
        self.operators: dict[str, BaseObfuscator] = {
            "OPI": OPIObfuscator(),
            "CFF": CFFObfuscator(),
            "ER": ERObfuscator(),
            "DE": DEObfuscator(),
            "JCI": JCIObfuscator(),
            "FS": FSObfuscator(),
        }

    def run_obfuscation(self, functions_df: pd.DataFrame, operator_names: list[str] | None = None):
        """Apply specified operators to a list of functions."""
        if operator_names is None:
            operator_names = list(self.operators.keys())
        
        results = []
        results_dir = Path(self.cfg.paths.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        log_path = results_dir / "obfuscation_log.jsonl"
        
        for _, row in functions_df.iterrows():
            func_meta = row.to_dict()
            source_file = Path(func_meta["source_file"])
            
            if not source_file.exists():
                logger.warning("Source file not found: %s", source_file)
                continue

            # Read function source
            try:
                # In a real implementation, we'd use the start/end lines to extract the function
                # For the skeleton, we'll read the whole file if it's small or just the range
                full_source = source_file.read_text(errors="ignore")
                lines = full_source.splitlines()
                func_source = "\n".join(lines[func_meta["start_line"]-1 : func_meta["end_line"]])
            except Exception as e:
                logger.error("Failed to read source for %s: %s", func_meta["name"], e)
                continue

            # Parse the function to get its AST node
            # For simplicity in the skeleton, we'll parse the function source directly
            tree = self.parser.parser.parse(func_source.encode())
            func_node = tree.root_node.children[0] if tree.root_node.children else tree.root_node

            for op_name in operator_names:
                if op_name not in self.operators:
                    logger.warning("Operator %s not found", op_name)
                    continue
                
                op = self.operators[op_name]
                eligible, reason = op.is_eligible(func_node, func_meta)
                
                if not eligible:
                    logger.debug("Function %s ineligible for %s: %s", func_meta["name"], op_name, reason)
                    continue
                
                # Apply transformation
                logger.info("Applying %s to %s", op_name, func_meta["name"])
                res = op.transform(func_source, func_node, func_meta, 
                                 seed=self.cfg.seed, intensity=1.0)
                
                # Record result
                results.append(res)
                with log_path.open("a") as f:
                    f.write(json.dumps(res.__dict__, default=str) + "\n")

        # Save summary
        if results:
            summary_df = pd.DataFrame([r.__dict__ for r in results])
            summary_df.to_csv(results_dir / "obfuscation_summary.csv", index=False)
            
            success_count = sum(1 for r in results if r.success)
            logger.info("Obfuscation complete. %d/%d operations successful.", 
                        success_count, len(results))
        else:
            logger.warning("No obfuscation operations performed.")
