"""Reinforcement Learning environment for SLOBF obfuscation search."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from slobf.config import SlobfConfig
from slobf.obfuscators.manager import ObfuscationManager
from slobf.compiler.manager import CompilerManager
from slobf.binary.extractor import BinaryExtractor
from slobf.models.manager import ModelManager
from slobf.metrics.calculator import MetricsCalculator

logger = logging.getLogger(__name__)

class ObfuscationEnv(gym.Env):
    """Gymnasium environment for obfuscation sequence search."""
    
    def __init__(self, cfg: SlobfConfig, functions_df: pd.DataFrame):
        super().__init__()
        self.cfg = cfg
        self.functions_df = functions_df
        
        # Obfuscation Managers
        self.obs_mgr = ObfuscationManager(cfg)
        self.comp_mgr = CompilerManager(cfg)
        self.extractor = BinaryExtractor()
        self.model_mgr = ModelManager(cfg)
        self.metrics_calc = MetricsCalculator(Path(cfg.paths.results_dir))
        
        # Action space: OPI, CFF, ER, DE, JCI, FS, STOP
        self.operators = list(self.obs_mgr.operators.keys())
        self.action_space = spaces.Discrete(len(self.operators) + 1)
        self.STOP_ACTION = len(self.operators)
        
        # State space (simplified for the skeleton)
        # current_step, multi-hot used, cs, cs_drop, growth, static_features
        self.observation_space = spaces.Box(low=0, high=10, shape=(20,), dtype=np.float32)
        
        self.max_steps = 5
        self.current_func = None
        self.current_source = ""
        self.orig_bin_func = None
        self.orig_compile = None
        self.state = None
        self.steps = 0
        self.used_ops = set()
        
        # Weights for Reward
        self.alpha = 1.0  # CS drop
        self.beta = 0.5   # Top-K bonus (placeholder)
        self.eta = 0.1    # Entropy bonus
        self.gamma = 0.4  # Code growth penalty
        self.rho = 0.2    # Instruction growth penalty
        self.tau = 0.05   # Step penalty
        self.fail_penalty = 2.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        # Select a random function from the dataframe
        self.current_func = self.functions_df.sample(n=1).iloc[0].to_dict()
        
        # Load original source and compile baseline
        source_path = Path(self.current_func["source_file"])
        self.current_source = source_path.read_text(errors="ignore")
        # Extract function source
        lines = self.current_source.splitlines()
        self.current_source = "\n".join(lines[self.current_func["start_line"]-1 : self.current_func["end_line"]])
        
        self.orig_compile = self.comp_mgr.compile_original(self.current_func["name"], source_path, "O0")
        self.orig_bin_func = None
        if self.orig_compile.success:
            self.orig_bin_func = self.extractor.extract_function(Path(self.orig_compile.binary_path), self.current_func["name"])
        
        self.steps = 0
        self.used_ops = set()
        self.state = self._get_obs(1.0, 0.0, 1.0) # Initial CS=1.0, Drop=0, Growth=1.0
        
        return self.state, {}

    def _get_obs(self, cs, cs_drop, growth):
        obs = np.zeros(20, dtype=np.float32)
        obs[0] = self.steps / self.max_steps
        obs[1] = cs
        obs[2] = cs_drop
        obs[3] = growth
        # Multi-hot used ops
        for op_idx in self.used_ops:
            if op_idx < 10:
                obs[4 + op_idx] = 1.0
        return obs

    def step(self, action):
        if action == self.STOP_ACTION or self.steps >= self.max_steps:
            return self.state, 0, True, False, {}

        self.steps += 1
        op_name = self.operators[action]
        op = self.obs_mgr.operators[op_name]
        
        # Check eligibility (mock node)
        eligible, reason = op.is_eligible(None, self.current_func)
        if not eligible:
            return self.state, -0.1, False, False, {"reason": reason}

        # Transform
        obs_res = op.transform(self.current_source, None, self.current_func, self.cfg.seed, 1.0)
        if not obs_res.success:
            return self.state, -0.5, False, False, {"reason": "transform_failed"}

        # Compile and Evaluate
        comp_res = self.comp_mgr.compile_obfuscated(obs_res.__dict__, "O0")
        if not comp_res.success:
            return self.state, -self.fail_penalty, True, False, {"reason": "compile_failed"}

        obs_bin_func = self.extractor.extract_function(Path(comp_res.binary_path), self.current_func["name"])
        if not obs_bin_func:
            return self.state, -self.fail_penalty, True, False, {"reason": "extraction_failed"}

        # Similarity (using mean of all enabled models)
        cs_drops = []
        for model_name, adapter in self.model_mgr.adapters.items():
            if not getattr(adapter, "enabled", False): continue
            e1 = adapter.embed(adapter.preprocess_function(self.orig_bin_func.__dict__)).embedding
            e2 = adapter.embed(adapter.preprocess_function(obs_bin_func.__dict__)).embedding
            if e1 is not None and e2 is not None:
                sim = adapter.similarity(e1, e2)
                cs_drops.append(1.0 - sim)
        
        avg_cs_drop = np.mean(cs_drops) if cs_drops else 0.0
        
        # Calculate Reward
        code_growth = (obs_res.inserted_lines - obs_res.removed_lines) / len(self.current_source.splitlines()) if self.current_source else 0
        instr_growth = obs_bin_func.instruction_count / self.orig_bin_func.instruction_count if self.orig_bin_func else 1.0
        
        reward = (self.alpha * avg_cs_drop - 
                  self.gamma * code_growth - 
                  self.rho * instr_growth - 
                  self.tau)
        
        # Update State
        self.used_ops.add(action)
        self.current_source = obs_res.changed_source
        self.state = self._get_obs(1.0 - avg_cs_drop, avg_cs_drop, instr_growth)
        
        return self.state, reward, False, False, {"cs_drop": avg_cs_drop}
