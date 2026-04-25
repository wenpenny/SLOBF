"""RL Agent and baseline strategies for RQ2."""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
from stable_baselines3 import PPO
from slobf.rl.env import ObfuscationEnv
from slobf.config import SlobfConfig

logger = logging.getLogger(__name__)

class RLAgent:
    def __init__(self, cfg: SlobfConfig, train_df: pd.DataFrame):
        self.cfg = cfg
        self.env = ObfuscationEnv(cfg, train_df)
        self.model = None

    def train(self, total_timesteps=10000):
        logger.info("Training RL agent (PPO) for %d timesteps...", total_timesteps)
        self.model = PPO("MlpPolicy", self.env, verbose=1)
        self.model.learn(total_timesteps=total_timesteps)
        
        model_path = Path(self.cfg.paths.results_dir) / "rq2" / "ppo_obfuscator"
        self.model.save(model_path)
        logger.info("RL agent trained and saved to %s", model_path)

    def predict(self, func_row: pd.Series):
        """Predict best obfuscation sequence for a function."""
        # For prediction, we use a single-function environment or manually step
        if self.model is None:
            return []
        
        # Reset env with specific function (requires env modification for precision)
        # Simplified: run the trained policy
        obs, _ = self.env.reset()
        sequence = []
        for _ in range(5):
            action, _states = self.model.predict(obs, deterministic=True)
            if action == self.env.STOP_ACTION:
                break
            sequence.append(self.env.operators[action])
            obs, reward, done, truncated, info = self.env.step(action)
            if done: break
        return sequence

class BaselineStrategies:
    def __init__(self, env: ObfuscationEnv):
        self.env = env

    def random_strategy(self, max_steps=4):
        sequence = []
        obs, _ = self.env.reset()
        for _ in range(max_steps):
            action = self.env.action_space.sample()
            if action == self.env.STOP_ACTION: break
            sequence.append(self.env.operators[action])
            obs, reward, done, truncated, info = self.env.step(action)
            if done: break
        return sequence

    def fixed_strategy(self, sequence=["JCI", "ER", "OPI", "CFF"]):
        obs, _ = self.env.reset()
        actual_seq = []
        for op_name in sequence:
            if op_name not in self.env.operators: continue
            action = self.env.operators.index(op_name)
            actual_seq.append(op_name)
            obs, reward, done, truncated, info = self.env.step(action)
            if done: break
        return actual_seq

    def greedy_strategy(self, max_steps=4):
        obs, _ = self.env.reset()
        sequence = []
        for _ in range(max_steps):
            best_reward = -float('inf')
            best_action = self.env.STOP_ACTION
            
            # Try all actions (brute force greedy)
            # This requires a 'virtual' step or state backup
            # For simplicity, we just pick the best looking one
            for action in range(len(self.env.operators)):
                # Mock step... (omitted for skeleton brevity)
                pass
            
            # Placeholder greedy
            action = 0 
            sequence.append(self.env.operators[action])
            obs, reward, done, truncated, info = self.env.step(action)
            if done: break
        return sequence
