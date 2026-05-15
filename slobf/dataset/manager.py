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
        if f.num_lines < 10:
            reasons.append("Too short (< 10 lines)")
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
        if reasons:
            f.ineligible_reason = "; ".join(reasons)
            f.eligibility = {"general": False}
        else:
            f.eligibility = {"general": True}
            # Per-operator eligibility (pre-computed so experiments can skip)
            f.eligibility["OPI"] = f.num_statements >= 2
            f.eligibility["CFF"] = (
                f.num_statements >= 5
                and not f.has_goto
                and not f.has_switch
                and not f.has_break
                and not f.has_continue
            )
            f.eligibility["ER"] = True
            f.eligibility["DE"] = True
            f.eligibility["JCI"] = f.num_statements >= 2
            f.eligibility["FS"] = (
                f.num_statements >= 8
                and not f.is_variadic
                and f.num_returns <= 1
            )

    def sample_functions(self, df: pd.DataFrame):
        """Split eligible functions into dataset / test-set shared by all RQs.

        - dataset (~80%): used by RQ2 to train the RL agent
        - testset (~20%): used by RQ1, RQ2 evaluation, and RQ3
        """
        if df.empty:
            return

        eligible = df[df["eligibility"].apply(lambda x: x.get("general", False))].copy()
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

        # Deterministic split by program + size_group to ensure balanced distribution
        dataset_parts = []
        testset_parts = []
        for (prog, sg), group in eligible.groupby(["program", "size_group"]):
            n_test = max(1, int(len(group) * 0.2))
            group_sorted = group.sort_values("name")
            testset_parts.append(group_sorted.iloc[:n_test])
            dataset_parts.append(group_sorted.iloc[n_test:])

        dataset = pd.concat(dataset_parts).sort_index()
        testset = pd.concat(testset_parts).sort_index()

        dataset.to_csv(results_dir / "selected_functions_dataset.csv", index=False)
        testset.to_csv(results_dir / "selected_functions_testset.csv", index=False)

        logger.info(
            "Split: dataset=%d testset=%d (total=%d)",
            len(dataset), len(testset), len(eligible),
        )
