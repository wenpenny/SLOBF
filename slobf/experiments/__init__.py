"""experiments — High-level RQ experiment runners.

Planned research questions:
  RQ1 — Individual operator impact: compile each operator in isolation
         across all opt levels and models; measure CS, Top-K, entropy.
  RQ2 — Operator combination robustness: enumerate k-combos (k=2,3);
         compare against single-operator baseline.
  RQ3 — RL-guided search: use reinforcement learning (slobf.rl) to
         find operator sequences that maximise evasion under a cost budget.

Public API (to be implemented):
  RQ1Runner(config).run() -> ExperimentResult
  RQ2Runner(config).run() -> ExperimentResult
  RQ3Runner(config).run() -> ExperimentResult
  ExperimentResult: metrics_df, summary_dict, plots
"""
