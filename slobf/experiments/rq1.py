"""RQ1: Impact of single obfuscation operators on binary similarity models."""

import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from slobf.config import SlobfConfig
from slobf.parser.c_parser import CParser, FunctionInfo
from slobf.obfuscators.manager import ObfuscationManager
from slobf.compiler.manager import CompilerManager
from slobf.binary.extractor import BinaryExtractor
from slobf.models.manager import ModelManager
from slobf.metrics.calculator import MetricsCalculator
from slobf.metrics.semantic import SemanticVerifier

logger = logging.getLogger(__name__)


class RQ1Runner:
    """Evaluate each operator independently on every eligible function."""

    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.rq1_dir = Path(cfg.paths.results_dir) / "rq1"
        self.rq1_dir.mkdir(parents=True, exist_ok=True)

        self.parser = CParser()
        self.obs_mgr = ObfuscationManager(cfg)
        self.comp_mgr = CompilerManager(cfg)
        self.extractor = BinaryExtractor()
        self.model_mgr = ModelManager(cfg)
        self.metrics = MetricsCalculator()
        self.verifier = SemanticVerifier(
            cc=cfg.compiler.cc, num_cases=cfg.metrics.semantic_test_cases
        )

    def run(self, seeds: list[int] | None = None):
        if seeds is None:
            seeds = [0, 1, 2]

        selected_csv = Path(self.cfg.paths.results_dir) / "selected_functions_testset.csv"
        if not selected_csv.exists():
            logger.error("selected_functions_testset.csv not found. Run 'slobf scan' first.")
            return

        df = pd.read_csv(selected_csv)
        operators = list(self.obs_mgr.operators.keys())
        raw_results = []

        self.model_mgr.setup_models()

        for _, row in tqdm(df.iterrows(), desc="RQ1", total=len(df)):
            func_info = FunctionInfo(**{k: row[k] for k in FunctionInfo.__dataclass_fields__
                                        if k in row})
            source_path = Path(func_info.source_file)
            program_dir = self._find_program_dir(source_path, func_info.program)

            if not source_path.exists():
                logger.warning("Source file not found: %s", source_path)
                continue
            if not program_dir or not program_dir.exists():
                logger.warning("Program directory not found for: %s", func_info.name)
                continue

            # --- Baseline: compile original, extract, embed ---
            baseline_binary = None
            baseline_func = None
            baseline_embs = {}

            baseline = self.comp_mgr.compile_baseline(program_dir, func_info.program, "O0")
            if baseline.success and baseline.binary_path:
                baseline_binary = Path(baseline.binary_path)
                baseline_func = self.extractor.extract_function(
                    baseline_binary, func_info.name, opt="O0"
                )
                if baseline_func:
                    for m_name, adapter in self.model_mgr.adapters.items():
                        inp = adapter.preprocess_function(baseline_func.to_dict())
                        emb_result = adapter.embed(inp)
                        if emb_result.success:
                            baseline_embs[m_name] = emb_result.embedding

            # --- Test each operator ---
            for op_name in operators:
                operator = self.obs_mgr.get_operator(op_name)
                eligible, reason = operator.is_eligible(func_info)
                if not eligible:
                    raw_results.append({
                        "function": func_info.name,
                        "program": func_info.program,
                        "operator": op_name,
                        "seed": 0,
                        "eligible": False,
                        "ineligible_reason": reason,
                    })
                    continue

                for seed in seeds:
                    entry = {
                        "function": func_info.name,
                        "program": func_info.program,
                        "operator": op_name,
                        "seed": seed,
                        "eligible": True,
                        "source_changed": False,
                        "compile_success": False,
                        "extraction_success": False,
                        "semantic_passed": False,
                        "binary_changed": False,
                        "cs": 1.0,
                        "cs_drop": 0.0,
                    }

                    # 1. Obfuscate in-place → get modified source
                    t0 = time.time()
                    obs_result = self.obs_mgr.obfuscate_function_in_file(
                        source_path, func_info, op_name, seed=seed, intensity=1.0
                    )
                    entry["obfuscation_time"] = time.time() - t0

                    if not obs_result or not obs_result.success:
                        entry["obfuscation_failed"] = True
                        raw_results.append(entry)
                        continue

                    entry["source_changed"] = obs_result.changed
                    entry["source_loc_growth"] = (
                        (obs_result.inserted_lines - obs_result.removed_lines)
                        / max(func_info.num_lines, 1)
                    )

                    # 2. Compile full program
                    t0 = time.time()
                    comp = self.comp_mgr.compile_obfuscated(
                        program_dir, func_info.program, func_info.name,
                        op_name, seed, "O0", source_path, obs_result.changed_source
                    )
                    entry["compile_time"] = time.time() - t0
                    entry["compile_success"] = comp.success
                    if comp.binary_size > 0:
                        entry["binary_size_growth"] = (
                            comp.binary_size / max(baseline.binary_size, 1)
                        )

                    if not comp.success or not comp.binary_path:
                        raw_results.append(entry)
                        continue

                    # 3. Extract function from binary
                    obs_func = self.extractor.extract_function(
                        Path(comp.binary_path), func_info.name, opt="O0",
                        operator=op_name, seed=seed,
                    )
                    entry["extraction_success"] = obs_func is not None
                    if obs_func:
                        # Binary change check
                        if baseline_func:
                            bh1 = baseline_func.compute_hashes()["instruction_hash"]
                            bh2 = obs_func.compute_hashes()["instruction_hash"]
                            entry["binary_changed"] = bh1 != bh2
                            diff_stats = self.metrics.binary_diff_stats(
                                baseline_func.to_dict(), obs_func.to_dict()
                            )
                            entry.update(diff_stats)

                        # 4. Semantic equivalence
                        obs_file = Path(comp.binary_path).parent / source_path.relative_to(program_dir)
                        if obs_file.exists():
                            sem_result = self.verifier.verify(
                                source_path, obs_file, func_info, seed=seed
                            )
                            entry["semantic_passed"] = sem_result.get("passed", False)
                            entry["semantic_cases"] = sem_result.get("total_cases", 0)

                        # 5. Model evaluation
                        for m_name, adapter in self.model_mgr.adapters.items():
                            if m_name not in baseline_embs:
                                continue
                            inp = adapter.preprocess_function(obs_func.to_dict())
                            emb_result = adapter.embed(inp)
                            if not emb_result.success:
                                continue
                            cs = adapter.similarity(baseline_embs[m_name], emb_result.embedding)
                            entry[f"cs_{m_name}"] = cs
                            entry[f"cs_drop_{m_name}"] = 1.0 - cs

                    raw_results.append(entry)

        # Save
        raw_df = pd.DataFrame(raw_results)
        raw_df.to_csv(self.rq1_dir / "single_operator_raw.csv", index=False)
        self._generate_summaries(raw_df)
        logger.info("RQ1 complete. Results in %s", self.rq1_dir)

    def _find_program_dir(self, source_file: Path, program_name: str) -> Path | None:
        """Given a source file path and program name, find the program root directory."""
        candidates = [source_file.parent]
        # Walk up until we find a directory matching program_name or hit datasets root
        for p in source_file.parents:
            if p.name == program_name:
                return p
            candidates.append(p)
        return Path(self.cfg.paths.datasets_dir) / "raw" / program_name

    def _generate_summaries(self, df: pd.DataFrame):
        if df.empty:
            return
        # By operator
        cs_cols = [c for c in df.columns if c.startswith("cs_drop_")]
        if cs_cols:
            df["cs_drop_avg"] = df[cs_cols].mean(axis=1)

        df.groupby("operator").agg({
            "source_changed": "mean",
            "compile_success": "mean",
            "extraction_success": "mean",
            "semantic_passed": "mean",
            "binary_changed": "mean",
        }).to_csv(self.rq1_dir / "summary_by_operator.csv")

        # Report
        report = self._build_report(df)
        (self.rq1_dir / "rq1_report.md").write_text(report, encoding="utf-8")

    def _build_report(self, df: pd.DataFrame) -> str:
        if df.empty:
            return "# RQ1 Report\n\nNo data collected."

        lines = ["# RQ1: Single Operator Impact", ""]
        for op in df["operator"].unique():
            op_df = df[df["operator"] == op]
            comp_rate = op_df["compile_success"].mean() * 100
            sem_rate = op_df["semantic_passed"].mean() * 100
            bin_chg = op_df["binary_changed"].mean() * 100
            lines.append(
                f"| {op} | {comp_rate:.0f}% | {sem_rate:.0f}% | {bin_chg:.0f}% |"
            )
        return "\n".join(lines)
