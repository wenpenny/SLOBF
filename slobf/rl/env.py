"""Reinforcement Learning environment for obfuscation sequence search."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

from slobf.config import SlobfConfig
from slobf.parser.c_parser import CParser, FunctionInfo
from slobf.obfuscators.manager import ObfuscationManager
from slobf.compiler.manager import CompilerManager
from slobf.binary.extractor import BinaryExtractor
from slobf.models.manager import ModelManager

logger = logging.getLogger(__name__)


class ObfuscationEnv(gym.Env):
    """Gymnasium environment for cost-aware obfuscation combination search.

    State:  [step/max_steps, cs_drop, code_growth, instr_growth, op0_used, ..., opN_used]
    Action: choice of operator or STOP (last action).
    Reward: cs_drop - λ_growth * code_growth - λ_instr * instr_growth - λ_step
    """

    def __init__(self, cfg: SlobfConfig, functions_df: pd.DataFrame):
        super().__init__()
        self.cfg = cfg
        self.functions_df = functions_df
        self.parser = CParser()
        self.obs_mgr = ObfuscationManager(cfg)
        self.comp_mgr = CompilerManager(cfg)
        self.extractor = BinaryExtractor()
        self.model_mgr = ModelManager(cfg)

        self.operators = list(self.obs_mgr.operators.keys())
        self.action_space = spaces.Discrete(len(self.operators) + 1)
        self.STOP_ACTION = len(self.operators)

        obs_dim = 4 + len(self.operators)
        self.observation_space = spaces.Box(low=-10, high=100, shape=(obs_dim,), dtype=np.float32)

        self.max_steps = 5

        # Reward weights
        self.alpha = 1.0   # CS drop reward
        self.gamma = 0.4   # code growth penalty
        self.rho = 0.2     # instruction growth penalty
        self.tau = 0.05    # step penalty
        self.fail_penalty = 2.0

        # State
        self.current_func: FunctionInfo | None = None
        self.current_source_path: Path | None = None
        self.current_program_dir: Path | None = None
        self.current_source: str = ""
        self.original_source: str = ""
        self.baseline_func = None
        self.steps = 0
        self.used_ops: set[int] = set()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        row = self.functions_df.sample(n=1, random_state=seed).iloc[0]

        self.current_func = FunctionInfo(**{k: row[k] for k in FunctionInfo.__dataclass_fields__
                                             if k in row})
        self.current_source_path = Path(self.current_func.source_file)
        self.current_source = self.current_source_path.read_text()
        self.original_source = self.current_source

        datasets_dir = Path(self.cfg.paths.datasets_dir) / "raw"
        self.current_program_dir = datasets_dir / self.current_func.program
        if not self.current_program_dir.exists():
            self.current_program_dir = self.current_source_path.parent

        # Baseline
        baseline = self.comp_mgr.compile_baseline(
            self.current_program_dir, self.current_func.program, "O0"
        )
        self.baseline_func = None
        if baseline.success and baseline.binary_path:
            self.baseline_func = self.extractor.extract_function(
                Path(baseline.binary_path), self.current_func.name, opt="O0"
            )

        self.steps = 0
        self.used_ops = set()
        return self._obs(1.0, 0.0, 1.0), {}

    def _obs(self, cs: float, cs_drop: float, instr_growth: float) -> np.ndarray:
        obs = np.zeros(4 + len(self.operators), dtype=np.float32)
        obs[0] = self.steps / self.max_steps
        obs[1] = cs
        obs[2] = cs_drop
        obs[3] = instr_growth
        for idx in self.used_ops:
            obs[4 + idx] = 1.0
        return obs

    def step(self, action: int):
        if action == self.STOP_ACTION or self.steps >= self.max_steps:
            return self._obs(1.0, 0.0, 1.0), 0.0, True, False, {}

        self.steps += 1
        op_name = self.operators[action]

        # Apply obfuscation
        result = self.obs_mgr.obfuscate_function_in_file(
            self.current_source_path, self.current_func,
            op_name, seed=self.cfg.seed, intensity=1.0,
        )
        if not result or not result.success:
            return self._obs(1.0, 0.0, 1.0), -0.5, False, False, {"reason": "transform_failed"}

        self.current_source = result.changed_source

        # Compile
        comp = self.comp_mgr.compile_obfuscated(
            self.current_program_dir, self.current_func.program,
            self.current_func.name, op_name, self.cfg.seed, "O0",
            self.current_source_path, result.changed_source,
        )
        if not comp.success or not comp.binary_path:
            return self._obs(1.0, 0.0, 1.0), -self.fail_penalty, True, False, {"reason": "compile_failed"}

        # Extract
        obs_func = self.extractor.extract_function(
            Path(comp.binary_path), self.current_func.name, opt="O0"
        )
        if obs_func is None:
            return self._obs(1.0, 0.0, 1.0), -self.fail_penalty, True, False, {"reason": "extraction_failed"}

        # Similarity
        cs_drops = []
        if self.baseline_func:
            for m_name, adapter in self.model_mgr.adapters.items():
                e1 = adapter.embed(adapter.preprocess_function(self.baseline_func.to_dict()))
                e2 = adapter.embed(adapter.preprocess_function(obs_func.to_dict()))
                if e1.success and e2.success:
                    sim = adapter.similarity(e1.embedding, e2.embedding)
                    cs_drops.append(1.0 - sim)

        avg_cs_drop = float(np.mean(cs_drops)) if cs_drops else 0.0

        # Growth metrics
        code_growth = (result.inserted_lines - result.removed_lines) / max(
            len(self.original_source.splitlines()), 1
        )
        instr_growth = (
            obs_func.instruction_count / max(self.baseline_func.instruction_count, 1)
            if self.baseline_func else 1.0
        )

        reward = (
            self.alpha * avg_cs_drop
            - self.gamma * code_growth
            - self.rho * instr_growth
            - self.tau
        )

        self.used_ops.add(action)
        self.current_func = FunctionInfo(
            name=self.current_func.name,
            source_file=str(self.current_source_path),
            program=self.current_func.program,
        )

        return self._obs(1.0 - avg_cs_drop, avg_cs_drop, instr_growth), reward, False, False, {"cs_drop": avg_cs_drop}
