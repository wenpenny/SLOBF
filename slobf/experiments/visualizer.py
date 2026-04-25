"""Visualization scripts for RQ1 results."""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

def plot_rq1_results(raw_csv: Path, output_dir: Path):
    """Generate charts for RQ1."""
    if not raw_csv.exists():
        logger.error("Raw CSV not found for plotting: %s", raw_csv)
        return

    df = pd.read_csv(raw_csv)
    if df.empty:
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    # 1. CS Drop by Operator (Bar Plot)
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x="operator", y="cs_drop", hue="model")
    plt.title("Cosine Similarity Drop by Operator and Model")
    plt.ylabel("Average CS Drop")
    plt.savefig(output_dir / "cs_drop_by_operator.png")
    plt.close()

    # 2. Valid Obfuscation Count
    plt.figure(figsize=(10, 6))
    valid_counts = df[df["model"] == df["model"].unique()[0]] # Count unique obfuscations
    sns.countplot(data=valid_counts, x="operator", hue="valid_obfuscation")
    plt.title("Obfuscation Success Rate by Operator")
    plt.savefig(output_dir / "obfuscation_success_rate.png")
    plt.close()

    # 3. Code Growth vs CS Drop (Scatter)
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x="instruction_count_growth", y="cs_drop", hue="operator", style="model")
    plt.title("Instruction Count Growth vs. CS Drop")
    plt.savefig(output_dir / "growth_vs_impact.png")
    plt.close()

    # 4. Model Sensitivity Heatmap
    pivot_df = df.pivot_table(index="operator", columns="model", values="cs_drop", aggfunc="mean")
    plt.figure(figsize=(8, 6))
    sns.heatmap(pivot_df, annot=True, cmap="YlOrRd")
    plt.title("Model Sensitivity Heatmap (CS Drop)")
    plt.savefig(output_dir / "model_sensitivity_heatmap.png")
    plt.close()

    logger.info("RQ1 plots generated in %s", output_dir)
