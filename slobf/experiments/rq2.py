"""RQ2: RL-guided cost-aware obfuscation combination search."""

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
from slobf.rl.agent import RLAgent, BaselineStrategies
from slobf.rl.env import ObfuscationEnv
from slobf.rl.cache import ObfuscationCache

logger = logging.getLogger(__name__)


class RQ2Runner:
    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.rq2_dir = Path(cfg.paths.results_dir) / "rq2"
        self.rq2_dir.mkdir(parents=True, exist_ok=True)
        self.cache = ObfuscationCache(self.rq2_dir / "cache")

        self.parser = CParser()
        self.obs_mgr = ObfuscationManager(cfg)
        self.comp_mgr = CompilerManager(cfg)
        self.extractor = BinaryExtractor()
        self.model_mgr = ModelManager(cfg)
        self.metrics = MetricsCalculator()

    def run(self, train_timesteps: int = 5000):
        train_csv = Path(self.cfg.paths.results_dir) / "selected_functions_rq2_train.csv"
        test_csv = Path(self.cfg.paths.results_dir) / "selected_functions_rq2_test.csv"

        if not train_csv.exists() or not test_csv.exists():
            logger.error("RQ2 CSVs not found. Run 'slobf scan' first.")
            return

        train_df = pd.read_csv(train_csv)
        test_df = pd.read_csv(test_csv)

        # Train RL agent
        logger.info("Training RL agent (%d timesteps)...", train_timesteps)
        agent = RLAgent(self.cfg, train_df)
        agent.train(total_timesteps=train_timesteps)

        # Evaluate on test set
        results = []
        self.model_mgr.setup_models()

        for _, row in tqdm(test_df.iterrows(), desc="RQ2 Eval", total=len(test_df)):
            func_info = FunctionInfo(**{k: row[k] for k in FunctionInfo.__dataclass_fields__
                                        if k in row})
            source_path = Path(func_info.source_file)

            if not source_path.exists():
                continue

            program_dir = Path(self.cfg.paths.datasets_dir) / "raw" / func_info.program
            if not program_dir.exists():
                program_dir = source_path.parent

            # RL strategy
            rl_seq = agent.predict(func_info)
            results.append(self._eval_sequence(func_info, source_path, program_dir,
                                                "RL-guided", rl_seq))

            # Baselines
            env = ObfuscationEnv(self.cfg, pd.DataFrame([row.to_dict()]))
            baselines = BaselineStrategies(env)
            results.append(self._eval_sequence(func_info, source_path, program_dir,
                                                "Random", baselines.random_strategy()))
            results.append(self._eval_sequence(func_info, source_path, program_dir,
                                                "Fixed", baselines.fixed_strategy()))
            results.append(self._eval_sequence(func_info, source_path, program_dir,
                                                "Greedy", []))

        res_df = pd.DataFrame(results)
        res_df.to_csv(self.rq2_dir / "rl_eval_raw.csv", index=False)
        self._generate_summaries(res_df)
        logger.info("RQ2 complete. Results in %s", self.rq2_dir)

    def _eval_sequence(self, func_info: FunctionInfo, source_path: Path,
                       program_dir: Path, strategy: str, sequence: list[str]) -> dict:
        """Apply a sequence of operators and evaluate."""
        entry = {
            "function": func_info.name,
            "program": func_info.program,
            "strategy": strategy,
            "sequence": " -> ".join(sequence) if sequence else "none",
            "length": len(sequence),
            "compile_success": False,
            "binary_changed": False,
        }

        current_source = source_path.read_text()
        current_path = source_path

        # Apply each operator in sequence
        for i, op_name in enumerate(sequence):
            obs_result = self.obs_mgr.obfuscate_function_in_file(
                current_path, func_info, op_name, seed=self.cfg.seed, intensity=1.0
            )
            if not obs_result or not obs_result.success:
                entry["obfuscation_failed"] = True
                entry["failed_at"] = op_name
                return entry
            current_source = obs_result.changed_source
            # Write modified source so the next operator sees accumulated changes
            if i < len(sequence) - 1:
                import tempfile
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".c", delete=False, dir=source_path.parent
                )
                tmp.write(current_source)
                tmp.close()
                current_path = Path(tmp.name)

        # Compile with the final modified source
        comp = self.comp_mgr.compile_obfuscated(
            program_dir, func_info.program, func_info.name,
            "combo", self.cfg.seed, "O0", source_path, current_source
        )
        entry["compile_success"] = comp.success
        entry["compile_time"] = comp.compile_time

        if comp.success and comp.binary_path:
            obs_func = self.extractor.extract_function(
                Path(comp.binary_path), func_info.name, opt="O0"
            )
            if obs_func:
                entry["binary_changed"] = True
                entry["instr_count"] = obs_func.instruction_count
                entry["bb_count"] = obs_func.bb_count

        return entry

    def _generate_summaries(self, df: pd.DataFrame):
        if df.empty:
            return
        df.groupby("strategy").agg({
            "compile_success": "mean",
            "length": "mean",
            "binary_changed": "mean",
        }).to_csv(self.rq2_dir / "strategy_comparison.csv")
