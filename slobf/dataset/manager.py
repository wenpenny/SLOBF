"""Dataset management and function screening for SLOBF."""

from __future__ import annotations

import json
import logging
from pathlib import Path

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

    def scan_all(self) -> pd.DataFrame:
        """Scan all programs and return a combined function inventory."""
        all_functions = []

        programs = [d for d in self.raw_dir.iterdir() if d.is_dir()]
        if not programs:
            logger.warning("No datasets/programs found in %s", self.raw_dir)
            return pd.DataFrame()

        for prog_path in programs:
            prog_name = prog_path.name
            logger.info("Scanning program: %s", prog_name)

            c_files = list(prog_path.rglob("*.c"))
            for c_file in tqdm(c_files, desc=f"Scanning {prog_name}", leave=False):
                funcs = self.parser.parse_file(c_file, program_name=prog_name)
                for f in funcs:
                    self._apply_screening(f)
                    all_functions.append(f.to_dict())

        df = pd.DataFrame(all_functions)

        results_dir = Path(self.cfg.paths.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)

        df.to_csv(results_dir / "function_inventory.csv", index=False)
        df.to_json(results_dir / "function_inventory.jsonl", orient="records", lines=True)

        eligible = df[df["eligibility"].apply(lambda x: x.get("general", False))]
        logger.info("Scan complete: %d functions (%d eligible)", len(df), len(eligible))

        summary = {
            "total_functions": len(df),
            "eligible_functions": len(eligible),
            "programs": df["program"].value_counts().to_dict(),
        }
        (results_dir / "dataset_summary.json").write_text(json.dumps(summary, indent=2))
        return df

    def _apply_screening(self, f: FunctionInfo):
        reasons = []
        if f.num_lines < 3:
            reasons.append("Too short (< 3 lines)")
        if f.num_statements < 3:
            reasons.append("Too few statements (< 3)")
        if f.num_statements <= 1 and f.num_returns == 1:
            reasons.append("Only return statement")
        if f.has_asm:
            reasons.append("Contains inline assembly")
        if f.is_variadic:
            reasons.append("Variadic function")
        if f.name == "main":
            reasons.append("main function")
        if f.has_goto:
            reasons.append("Contains goto")

        if reasons:
            f.ineligible_reason = "; ".join(reasons)
            f.eligibility = {"general": False}
        else:
            f.eligibility = {"general": True}

    def sample_functions(self, df: pd.DataFrame):
        """Split eligible functions into train/test sets shared by all RQs.

        - Train (~80%): used by RQ2 to train the RL agent
        - Test  (~20%): used by RQ1, RQ2 evaluation, and RQ3
        """
        if df.empty:
            return

        eligible = df[df["eligibility"].apply(lambda x: x.get("general", False))].copy()
        # Deduplicate: same function name in same source file (macro expansions)
        eligible = eligible.drop_duplicates(subset=["name", "source_file"])
        if eligible.empty:
            logger.warning("No eligible functions found.")
            return

        eligible["size_group"] = pd.cut(
            eligible["num_statements"],
            bins=[0, 10, 50, float("inf")],
            labels=["small", "medium", "large"],
        )
        eligible["is_complex"] = eligible["num_branches"] + eligible["num_loops"] > 5

        results_dir = Path(self.cfg.paths.results_dir)

        # --- Train / test split ---
        from sklearn.model_selection import train_test_split
        try:
            train, test = train_test_split(
                eligible, test_size=0.2,
                stratify=eligible[["size_group", "program"]],
                random_state=self.cfg.seed,
            )
        except Exception:
            train, test = train_test_split(eligible, test_size=0.2, random_state=self.cfg.seed)

        train.to_csv(results_dir / "selected_functions_train.csv", index=False)
        test.to_csv(results_dir / "selected_functions_test.csv", index=False)

        # --- RQ1: sample from test set ---
        rq1_size = min(len(test), 1000)
        rq1 = test.sample(rq1_size, random_state=self.cfg.seed)
        rq1.to_csv(results_dir / "selected_functions_rq1.csv", index=False)

        logger.info(
            "Split: train=%d test=%d (total=%d) | RQ1 sample=%d",
            len(train), len(test), len(eligible), len(rq1),
        )
