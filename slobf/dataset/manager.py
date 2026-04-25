"""Dataset management and function screening for SLOBF."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from slobf.parser.c_parser import CParser, FunctionInfo
from slobf.config import SlobfConfig

logger = logging.getLogger(__name__)

class DatasetManager:
    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.parser = CParser()
        self.raw_dir = Path(cfg.paths.datasets_dir) / "raw"
        self.meta_dir = Path(cfg.paths.datasets_dir) / "metadata"
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def scan_all(self) -> pd.DataFrame:
        """Scan all datasets and return a combined function inventory."""
        all_functions = []
        
        datasets = [d for d in self.raw_dir.iterdir() if d.is_dir()]
        if not datasets:
            logger.warning("No datasets found in %s", self.raw_dir)
            return pd.DataFrame()

        for ds_path in datasets:
            ds_name = ds_path.name
            logger.info("Scanning dataset: %s", ds_name)
            
            c_files = list(ds_path.rglob("*.c"))
            for c_file in tqdm(c_files, desc=f"Scanning {ds_name}"):
                funcs = self.parser.parse_file(c_file, ds_name)
                for f in funcs:
                    self._apply_screening(f)
                    all_functions.append(f.to_dict())

        df = pd.DataFrame(all_functions)
        
        # Save results to results/
        results_dir = Path(self.cfg.paths.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        inventory_csv = results_dir / "function_inventory.csv"
        df.to_csv(inventory_csv, index=False)
        
        inventory_jsonl = results_dir / "function_inventory.jsonl"
        df.to_json(inventory_jsonl, orient="records", lines=True)

        # Save metadata to datasets/metadata/
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.meta_dir / "functions.csv", index=False)
        
        # Program metadata
        programs = df[["dataset", "source_file"]].drop_duplicates()
        programs.to_csv(self.meta_dir / "programs.csv", index=False)
        
        # Summary
        summary = {
            "total_functions": len(df),
            "eligible_functions": int(df["eligibility"].apply(lambda x: x.get("general", False)).sum()),
            "datasets": df["dataset"].value_counts().to_dict(),
            "timestamp": pd.Timestamp.now().isoformat()
        }
        with (self.meta_dir / "dataset_summary.json").open("w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info("Scan complete. Found %d functions. Saved to %s", len(df), inventory_csv)
        return df

    def _apply_screening(self, f: FunctionInfo):
        """Apply general screening rules to determine eligibility."""
        reasons = []
        
        # 1. 函数体少于 3 行
        if f.num_lines < 3:
            reasons.append("Too short (< 3 lines)")
            
        # 2. 有效语句少于 3 条
        if f.num_statements < 3:
            reasons.append("Too few statements (< 3)")
            
        # 3. 只有一个 return 语句且无局部计算 (num_statements includes return usually, so 1 statement)
        if f.num_statements <= 1 and f.num_returns == 1:
            reasons.append("Only return statement")
            
        # 5. 包含内联汇编 asm
        if f.has_asm:
            reasons.append("Contains asm")
            
        # 10. 变参函数默认不混淆
        if f.is_variadic:
            reasons.append("Variadic function")
            
        # 11. main
        if f.name == "main":
            reasons.append("main function")

        if reasons:
            f.ineligible_reason = "; ".join(reasons)
            f.eligibility = {"general": False}
        else:
            f.eligibility = {"general": True}

    def sample_functions(self, df: pd.DataFrame):
        """Sample functions for different RQs based on stratified rules."""
        if df.empty:
            return

        eligible = df[df["eligibility"].apply(lambda x: x.get("general", False))].copy()
        
        if eligible.empty:
            logger.warning("No eligible functions found after screening.")
            return

        # Add stratification columns
        eligible["size_group"] = pd.cut(eligible["num_statements"], 
                                        bins=[0, 10, 50, float('inf')], 
                                        labels=["small", "medium", "large"])
        
        eligible["is_complex"] = eligible["num_branches"] + eligible["num_loops"] > 5
        
        results_dir = Path(self.cfg.paths.results_dir)

        # Stratified sampling for RQ1
        # Try to get 100 from each size group if possible
        rq1_samples = []
        for group in ["small", "medium", "large"]:
            group_df = eligible[eligible["size_group"] == group]
            if not group_df.empty:
                rq1_samples.append(group_df.sample(min(len(group_df), 333), random_state=self.cfg.seed))
        
        rq1_final = pd.concat(rq1_samples) if rq1_samples else eligible.sample(min(len(eligible), 1000))
        rq1_final.to_csv(results_dir / "selected_functions_rq1.csv", index=False)

        # RQ2: Train/Test split (stratified by size and complexity)
        from sklearn.model_selection import train_test_split
        try:
            train, test = train_test_split(eligible, test_size=0.2, 
                                         stratify=eligible[["size_group", "is_complex"]],
                                         random_state=self.cfg.seed)
        except Exception:
            # Fallback if stratification fails (e.g. too few samples in some strata)
            train = eligible.sample(frac=0.8, random_state=self.cfg.seed)
            test = eligible.drop(train.index)

        train.to_csv(results_dir / "selected_functions_rq2_train.csv", index=False)
        test.to_csv(results_dir / "selected_functions_rq2_test.csv", index=False)

        # RQ3: RL search (smaller set for efficiency)
        rq3_sample = eligible.sample(min(len(eligible), 200), random_state=self.cfg.seed)
        rq3_sample.to_csv(results_dir / "selected_functions_rq3.csv", index=False)

        logger.info("Sampling complete. Samples saved to %s", results_dir)
