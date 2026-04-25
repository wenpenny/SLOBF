"""reports — Result aggregation, CSV/JSON export, and plotting.

Planned responsibilities:
  - Aggregate per-function JSONL events into summary DataFrames
  - Export CSV tables for each RQ
  - Generate matplotlib figures (heatmaps, bar charts, violin plots)
  - Produce a LaTeX-ready table skeleton

Public API (to be implemented):
  ReportGenerator(results_dir).generate(output_dir) -> None
  plot_rq1_heatmap(df, output_path) -> None
  plot_rq2_combo_matrix(df, output_path) -> None
  plot_rq3_reward_curve(df, output_path) -> None
"""
