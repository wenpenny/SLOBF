"""Visualization for SLOBF experiment results."""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)


def plot_rq1_results(raw_csv: Path, output_dir: Path):
    """Generate RQ1 charts: CS drop by operator, heatmaps, growth vs impact."""
    if not raw_csv.exists():
        logger.error("Raw CSV not found: %s", raw_csv)
        return

    df = pd.read_csv(raw_csv)
    if df.empty:
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    # 1. Compile and extraction success by operator
    if "operator" in df.columns:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        rates = df.groupby("operator").agg({
            "compile_success": "mean",
            "extraction_success": "mean",
            "semantic_passed": "mean",
            "binary_changed": "mean",
        })
        rates.plot(kind="bar", ax=axes[0])
        axes[0].set_title("Success Rates by Operator")
        axes[0].set_ylabel("Rate")
        axes[0].set_ylim(0, 1.05)

        if "binary_changed" in rates.columns:
            rates[["binary_changed"]].plot(kind="bar", ax=axes[1], color="orange")
            axes[1].set_title("Binary Changed Rate")
            axes[1].set_ylim(0, 1.05)

        plt.tight_layout()
        plt.savefig(output_dir / "operator_success_rates.png", dpi=150)
        plt.close()

    # 2. CS Drop heatmap (if model columns exist)
    cs_cols = [c for c in df.columns if c.startswith("cs_drop_")]
    if cs_cols and "operator" in df.columns:
        plt.figure(figsize=(10, 6))
        heat = df.groupby("operator")[cs_cols].mean()
        heat.columns = [c.replace("cs_drop_", "") for c in cs_cols]
        sns.heatmap(heat, annot=True, cmap="YlOrRd", fmt=".3f")
        plt.title("Model Sensitivity Heatmap (avg CS Drop)")
        plt.tight_layout()
        plt.savefig(output_dir / "model_sensitivity_heatmap.png", dpi=150)
        plt.close()

    # 3. Growth vs Impact scatter
    if "instr_growth_ratio" in df.columns and cs_cols:
        plt.figure(figsize=(10, 6))
        df["cs_drop_avg"] = df[cs_cols].mean(axis=1)
        sns.scatterplot(
            data=df, x="instr_growth_ratio", y="cs_drop_avg",
            hue="operator", style=df["compile_success"].astype(str),
        )
        plt.title("Instruction Growth vs CS Drop")
        plt.xlabel("Instruction Growth Ratio")
        plt.ylabel("Average CS Drop")
        plt.tight_layout()
        plt.savefig(output_dir / "growth_vs_impact.png", dpi=150)
        plt.close()

    logger.info("RQ1 plots saved to %s", output_dir)
