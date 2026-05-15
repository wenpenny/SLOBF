"""RQ3: Impact of compiler optimization levels on obfuscation effectiveness."""

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from slobf.config import SlobfConfig
from slobf.parser.c_parser import FunctionInfo
from slobf.obfuscators.manager import ObfuscationManager
from slobf.compiler.manager import CompilerManager
from slobf.binary.extractor import BinaryExtractor
from slobf.models.manager import ModelManager
from slobf.metrics.calculator import MetricsCalculator

logger = logging.getLogger(__name__)


class RQ3Runner:
    """Evaluate how O0–O3 affect obfuscation survival."""

    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.rq3_dir = Path(cfg.paths.results_dir) / "rq3"
        self.rq3_dir.mkdir(parents=True, exist_ok=True)

        self.obs_mgr = ObfuscationManager(cfg)
        self.comp_mgr = CompilerManager(cfg)
        self.extractor = BinaryExtractor()
        self.model_mgr = ModelManager(cfg)
        self.metrics = MetricsCalculator()

    def run(self, functions_csv: str | None = None):
        if functions_csv is None:
            functions_csv = str(Path(self.cfg.paths.results_dir) / "selected_functions_test.csv")
        df = pd.read_csv(functions_csv)
        opt_levels = self.cfg.compiler.opt_levels
        operators = list(self.obs_mgr.operators.keys())
        results = []

        self.model_mgr.setup_models()

        for _, row in tqdm(df.iterrows(), desc="RQ3", total=len(df)):
            func_info = FunctionInfo(**{k: row[k] for k in FunctionInfo.__dataclass_fields__
                                        if k in row})
            source_path = Path(func_info.source_file)
            program_dir = Path(self.cfg.paths.datasets_dir) / "raw" / func_info.program
            if not program_dir.exists():
                program_dir = source_path.parent

            if not source_path.exists():
                continue

            for opt in opt_levels:
                # --- Baseline at this opt level ---
                baseline = self.comp_mgr.compile_baseline(program_dir, func_info.program, opt)
                baseline_func = None
                if baseline.success and baseline.binary_path:
                    baseline_func = self.extractor.extract_function(
                        Path(baseline.binary_path), func_info.name, opt=opt
                    )

                for op_name in operators:
                    entry = {
                        "function": func_info.name,
                        "program": func_info.program,
                        "operator": op_name,
                        "opt": opt,
                        "extraction_success": False,
                        "binary_changed": False,
                        "cs_drop": 0.0,
                    }

                    # Record if baseline was already inlined
                    if baseline_func is None:
                        entry["failure_reason"] = "baseline_inlined"
                        results.append(entry)
                        continue

                    # Obfuscate
                    obs_result = self.obs_mgr.obfuscate_function_in_file(
                        source_path, func_info, op_name,
                        seed=self.cfg.seed, intensity=1.0,
                    )
                    if not obs_result or not obs_result.success:
                        entry["failure_reason"] = "obfuscation_failed"
                        results.append(entry)
                        continue

                    # Compile at this opt level
                    comp = self.comp_mgr.compile_obfuscated(
                        program_dir, func_info.program, func_info.name,
                        op_name, self.cfg.seed, opt, source_path,
                        obs_result.changed_source,
                    )
                    entry["compile_success"] = comp.success

                    if not comp.success or not comp.binary_path:
                        entry["failure_reason"] = "compile_failed"
                        results.append(entry)
                        continue

                    # Extract obfuscated function
                    obs_func = self.extractor.extract_function(
                        Path(comp.binary_path), func_info.name, opt=opt,
                        operator=op_name,
                    )
                    entry["extraction_success"] = obs_func is not None

                    if obs_func is None:
                        entry["failure_reason"] = "inlined_or_stripped"
                        results.append(entry)
                        continue

                    # Compare
                    bh1 = baseline_func.compute_hashes()["instruction_hash"]
                    bh2 = obs_func.compute_hashes()["instruction_hash"]
                    entry["binary_changed"] = bh1 != bh2

                    diff = self.metrics.binary_diff_stats(
                        baseline_func.to_dict(), obs_func.to_dict()
                    )
                    entry.update(diff)

                    # Model eval
                    for m_name, adapter in self.model_mgr.adapters.items():
                        e1 = adapter.embed(adapter.preprocess_function(baseline_func.to_dict()))
                        e2 = adapter.embed(adapter.preprocess_function(obs_func.to_dict()))
                        if e1.success and e2.success:
                            cs = adapter.similarity(e1.embedding, e2.embedding)
                            entry[f"cs_{m_name}"] = cs
                            entry[f"cs_drop_{m_name}"] = 1.0 - cs

                    results.append(entry)

        res_df = pd.DataFrame(results)
        res_df.to_csv(self.rq3_dir / "optimization_raw.csv", index=False)
        self._generate_summaries(res_df)
        logger.info("RQ3 complete. Results in %s", self.rq3_dir)

    def _generate_summaries(self, df: pd.DataFrame):
        if df.empty:
            return
        df.groupby(["operator", "opt"]).agg({
            "extraction_success": "mean",
            "binary_changed": "mean",
        }).to_csv(self.rq3_dir / "summary_by_operator_opt.csv")

        df.groupby("opt").agg({
            "extraction_success": "mean",
            "binary_changed": "mean",
        }).to_csv(self.rq3_dir / "summary_by_opt.csv")
