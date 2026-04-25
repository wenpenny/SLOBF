"""RQ1 Experiment Orchestrator for SLOBF."""

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

from slobf.config import SlobfConfig
from slobf.obfuscators.manager import ObfuscationManager
from slobf.compiler.manager import CompilerManager
from slobf.binary.extractor import BinaryExtractor
from slobf.models.manager import ModelManager
from slobf.metrics.calculator import MetricsCalculator

logger = logging.getLogger(__name__)

class RQ1Runner:
    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.rq1_dir = Path(cfg.paths.results_dir) / "rq1"
        self.rq1_dir.mkdir(parents=True, exist_ok=True)
        
        self.obs_mgr = ObfuscationManager(cfg)
        self.comp_mgr = CompilerManager(cfg)
        self.extractor = BinaryExtractor()
        self.model_mgr = ModelManager(cfg)
        self.metrics_calc = MetricsCalculator(Path(cfg.paths.results_dir))

    def run(self, seeds=[0, 1, 2]):
        logger.info("Starting RQ1 Experiment...")
        
        # 1. Load selected functions
        selected_csv = Path(self.cfg.paths.results_dir) / "selected_functions_rq1.csv"
        if not selected_csv.exists():
            logger.error("selected_functions_rq1.csv not found")
            return
        
        df = pd.read_csv(selected_csv)
        raw_results = []
        eligibility_data = []

        # 2. Iterate through each function, operator, and seed
        operators = list(self.obs_mgr.operators.keys())
        
        for _, row in tqdm(df.iterrows(), desc="RQ1 Functions", total=len(df)):
            func_meta = row.to_dict()
            
            # Extract original source once
            try:
                source_path = Path(func_meta["source_file"])
                full_source = source_path.read_text(errors="ignore")
                lines = full_source.splitlines()
                func_source = "\n".join(lines[func_meta["start_line"]-1 : func_meta["end_line"]])
            except Exception as e:
                logger.error("Failed to read source for %s: %s", func_meta["name"], e)
                continue

            # Original binary info (needed for baseline)
            # We'll compile the original O0 once
            orig_compile = self.comp_mgr.compile_original(func_meta["name"], source_path, "O0")
            orig_bin_func = None
            if orig_compile.success:
                orig_bin_func = self.extractor.extract_function(Path(orig_compile.binary_path), func_meta["name"])

            for op_name in operators:
                op = self.obs_mgr.operators[op_name]
                
                # Eligibility check (independent of seed)
                # In a real setup, we'd need to parse the AST node properly
                # For this orchestrator, we'll mock the node or use a placeholder
                # as is_eligible in our current implementation is mostly meta-based.
                eligible, reason = op.is_eligible(None, func_meta)
                eligibility_data.append({
                    "dataset": func_meta.get("dataset"),
                    "program": func_meta.get("program"),
                    "function": func_meta["name"],
                    "operator": op_name,
                    "eligible": eligible,
                    "ineligible_reason": reason
                })

                if not eligible:
                    continue

                for seed in seeds:
                    start_obs = time.time()
                    obs_res = op.transform(func_source, None, func_meta, seed, 1.0)
                    obs_time = time.time() - start_obs
                    
                    if not obs_res.success:
                        continue
                    
                    # 5. Compile O0
                    comp_res = self.comp_mgr.compile_obfuscated(obs_res.__dict__, "O0")
                    
                    # 6. Extract Binary
                    obs_bin_func = None
                    if comp_res.success:
                        obs_bin_func = self.extractor.extract_function(Path(comp_res.binary_path), func_meta["name"])
                    
                    # 7. Binary Changed check
                    binary_changed = False
                    if orig_bin_func and obs_bin_func:
                        binary_changed = (orig_bin_func.compute_hashes()["instruction_hash"] != 
                                          obs_bin_func.compute_hashes()["instruction_hash"])

                    # 8-10. Model Evaluation (simplified for orchestrator)
                    # In real RQ1, we'd batch this, but for now we do it per entry
                    models = ["PalmTree", "JTrans", "CEBin"] # CLAP is disabled
                    for model_name in models:
                        adapter = self.model_mgr.adapters[model_name]
                        adapter.setup() # Ensure setup
                        
                        cs = 0.0
                        if orig_bin_func and obs_bin_func:
                            # Use mock embeddings if weights aren't loaded
                            e1 = adapter.embed(adapter.preprocess_function(orig_bin_func.__dict__)).embedding
                            e2 = adapter.embed(adapter.preprocess_function(obs_bin_func.__dict__)).embedding
                            if e1 is not None and e2 is not None:
                                cs = adapter.similarity(e1, e2)

                        # Record everything
                        raw_results.append({
                            "dataset": func_meta.get("dataset"),
                            "program": func_meta.get("program"),
                            "function": func_meta["name"],
                            "operator": op_name,
                            "seed": seed,
                            "eligible": eligible,
                            "source_changed": obs_res.changed,
                            "compile_success": comp_res.success,
                            "extraction_success": obs_bin_func is not None,
                            "binary_changed": binary_changed,
                            "valid_obfuscation": eligible and comp_res.success and binary_changed,
                            "model": model_name,
                            "cs": cs,
                            "cs_drop": 1.0 - cs,
                            "source_loc_growth": (obs_res.inserted_lines - obs_res.removed_lines) / len(func_source.splitlines()) if func_source else 0,
                            "instruction_count_growth": obs_bin_func.instruction_count / orig_bin_func.instruction_count if orig_bin_func and obs_bin_func else 1.0,
                            "binary_size_growth": comp_res.binary_size / orig_compile.binary_size if orig_compile.success and comp_res.success else 1.0,
                            "obfuscation_time": obs_time,
                            "compile_time": comp_res.compile_time,
                            "opcode_entropy_before": self.metrics_calc.calculate_entropy(orig_bin_func.opcodes) if orig_bin_func else 0,
                            "opcode_entropy_after": self.metrics_calc.calculate_entropy(obs_bin_func.opcodes) if obs_bin_func else 0,
                        })

        # Save results
        pd.DataFrame(eligibility_data).to_csv(self.rq1_dir / "operator_eligibility.csv", index=False)
        raw_df = pd.DataFrame(raw_results)
        raw_df.to_csv(self.rq1_dir / "single_operator_raw.csv", index=False)
        
        # 3. Generate Summaries
        self.generate_summaries(raw_df)
        self.generate_report(raw_df)
        logger.info("RQ1 Experiment completed. Results in %s", self.rq1_dir)

    def generate_summaries(self, df):
        if df.empty: return
        
        # By Operator
        df.groupby("operator").agg({
            "cs": ["mean", "std"],
            "cs_drop": "mean",
            "valid_obfuscation": "sum",
            "instruction_count_growth": "mean"
        }).to_csv(self.rq1_dir / "single_operator_summary_by_operator.csv")

        # By Model
        df.groupby("model").agg({
            "cs": ["mean", "std"],
            "cs_drop": "mean"
        }).to_csv(self.rq1_dir / "single_operator_summary_by_model.csv")

        # By Dataset
        df.groupby("dataset").agg({
            "cs": "mean",
            "valid_obfuscation": "sum"
        }).to_csv(self.rq1_dir / "single_operator_summary_by_dataset.csv")

    def generate_report(self, df):
        report_path = self.rq1_dir / "rq1_report.md"
        if df.empty:
            report_path.write_text("# RQ1 Report\n\nNo data collected.")
            return

        summary_op = df.groupby("operator")["cs_drop"].mean().sort_values(ascending=False)
        top_op = summary_op.index[0]
        
        # Calculate most sensitive model
        summary_model = df.groupby("model")["cs_drop"].mean().sort_values(ascending=False)
        top_model = summary_model.index[0]

        # Calculate best obfuscation rate
        summary_valid = df.groupby("operator")["valid_obfuscation"].mean().sort_values(ascending=False)
        best_valid_op = summary_valid.index[0]

        report = f"""# RQ1 实验报告: 源码级混淆对二进制相似性模型的影响

## 1. 核心发现
- **对相似性影响最大的算子**: `{top_op}`，其平均 CS drop 达到了 {summary_op.iloc[0]:.4f}。
- **最敏感的模型**: `{top_model}`，在该模型上观察到的平均 CS drop 最高 ({summary_model.iloc[0]:.4f})。
- **真实混淆成功率最高的算子**: `{best_valid_op}`，其有效混淆率（通过编译且二进制发生改变）为 {summary_valid.iloc[0]*100:.2f}%。
- **全局有效混淆率**: 实验涉及的所有算子全局平均有效混淆率为 {df['valid_obfuscation'].mean()*100:.2f}%。

## 2. 算子有效性与代价分析
下表展示了各算子在 O0 编译条件下的表现：

| 算子 | 平均 CS Drop | 指令数增长率 | 二进制大小增长 | 有效混淆率 |
|------|--------------|--------------|----------------|------------|
"""
        for op in summary_op.index:
            op_df = df[df["operator"] == op]
            drop = op_df["cs_drop"].mean()
            instr_growth = op_df["instruction_count_growth"].mean()
            bin_growth = op_df["binary_size_growth"].mean()
            valid_rate = op_df["valid_obfuscation"].mean()
            report += f"| {op} | {drop:.4f} | {instr_growth:.2f}x | {bin_growth:.2f}x | {valid_rate*100:.1f}% |\n"

        report += f"""
## 3. 模型敏感性对比
不同模型对源码级混淆的鲁棒性存在差异：
"""
        for model, drop in summary_model.items():
            report += f"- **{model}**: 平均 CS drop 为 {drop:.4f}。{' (最为敏感)' if model == top_model else ''}\n"

        report += """
## 4. 结论与讨论
- **代码增长与影响的权衡**: 通过分析 `growth_vs_impact.png`，我们可以观察到代码增长率与 CS drop 之间的相关性。
- **编译与提取失败的影响**: 实验中记录了部分失败情况。若有效混淆率较低，可能是由于算子筛选规则（Eligibility）与 GCC 优化行为之间的冲突。
- **后续建议**: 针对表现最强的算子组合，可以在 RQ2 中进一步探索其多重叠加的效果。

---
*报告生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}*
"""
        report_path.write_text(report, encoding="utf-8")
