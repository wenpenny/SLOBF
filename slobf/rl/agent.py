"""RL Agent and baseline strategies for obfuscation sequence search."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from stable_baselines3 import PPO

from slobf.config import SlobfConfig
from slobf.parser.c_parser import FunctionInfo
from slobf.rl.env import ObfuscationEnv

logger = logging.getLogger(__name__)


class RLAgent:
    """PPO-based agent for obfuscation sequence optimisation."""

    def __init__(self, cfg: SlobfConfig, train_df: pd.DataFrame):
        self.cfg = cfg
        self.env = ObfuscationEnv(cfg, train_df)
        self.model = None
        self.operators = list(self.env.operators)

    def train(self, total_timesteps: int = 10000):
        logger.info("Training PPO agent for %d timesteps...", total_timesteps)
        self.model = PPO("MlpPolicy", self.env, verbose=1)
        self.model.learn(total_timesteps=total_timesteps)

        model_path = Path(self.cfg.paths.results_dir) / "rq2" / "ppo_obfuscator"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save(str(model_path))
        logger.info("Agent saved to %s", model_path)

    def predict(self, func_info: FunctionInfo) -> list[str]:
        """Return the best obfuscation sequence for a function."""
        if self.model is None:
            return []
        obs, _ = self.env.reset()
        seq = []
        for _ in range(5):
            action, _ = self.model.predict(obs, deterministic=True)
            if action == self.env.STOP_ACTION:
                break
            seq.append(self.operators[action])
            obs, reward, done, _, _ = self.env.step(action)
            if done:
                break
        return seq

    def load(self, path: str):
        self.model = PPO.load(path, env=self.env)


class BaselineStrategies:
    """Baseline strategies for RQ2 comparison."""

    def __init__(self, env: ObfuscationEnv):
        self.env = env
        self.operators = env.operators

    def random_strategy(self, max_steps: int = 3) -> list[str]:
        obs, _ = self.env.reset()
        seq = []
        for _ in range(max_steps):
            action = self.env.action_space.sample()
            if action == self.env.STOP_ACTION:
                break
            seq.append(self.operators[action])
            obs, reward, done, _, _ = self.env.step(action)
            if done:
                break
        return seq

    def fixed_strategy(self) -> list[str]:
        """Pre-defined sequence: JCI -> ER -> OPI."""
        seq = []
        for op_name in ["JCI", "ER", "OPI"]:
            if op_name in self.operators:
                seq.append(op_name)
        return seq

    def greedy_strategy(self, max_steps: int = 3) -> list[str]:
        """Iteratively pick the single operator with best reward."""
        obs, _ = self.env.reset()
        seq = []
        for _ in range(max_steps):
            best_reward = -float("inf")
            best_action = self.env.STOP_ACTION
            for a in range(len(self.operators)):
                # Re-create env to simulate each action independently
                temp_env = ObfuscationEnv(self.env.cfg, self.env.functions_df)
                temp_obs, _ = temp_env.reset()
                # Apply prior sequence
                for prior_a in seq:
                    if prior_a in temp_env.operators:
                        idx = temp_env.operators.index(prior_a)
                        temp_obs, r, d, _, _ = temp_env.step(idx)
                        if d:
                            break
                temp_obs, r, d, _, _ = temp_env.step(a)
                if r > best_reward:
                    best_reward = r
                    best_action = a

            if best_action == self.env.STOP_ACTION or best_reward <= 0:
                break
            seq.append(self.operators[best_action])
            obs, reward, done, _, _ = self.env.step(best_action)
            if done:
                break
        return seq
