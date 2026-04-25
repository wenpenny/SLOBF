"""rl — Reinforcement learning search for obfuscation operator sequences.

Planned approach:
  - State: current operator combo applied to a function
  - Action: add / remove / swap one operator
  - Reward: evasion_gain - lambda * overhead_cost
  - Algorithm: PPO or DQN (torch-based, CPU-friendly for small action spaces)
  - Also supports random search and greedy hill-climbing as baselines

Public API (to be implemented):
  RLSearchAgent(config).search(function_pool) -> list[ObfuscationPolicy]
  ObfuscationPolicy: operators, expected_reward, overhead_estimate
"""
