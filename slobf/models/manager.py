"""Manager for running model evaluations in SLOBF."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

from slobf.config import SlobfConfig
from slobf.models.adapters.cebin import CEBinAdapter
from slobf.models.adapters.jtrans import JTransAdapter
from slobf.models.adapters.clap import CLAPAdapter
from slobf.models.adapters.palmtree import PalmTreeAdapter
from slobf.models.base import ModelAdapter

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.results_dir = Path(cfg.paths.results_dir)
        self.workdir = Path(cfg.paths.workdir)
        self.adapters: dict[str, ModelAdapter] = {
            "CEBin": CEBinAdapter(cfg.models.cebin_path if hasattr(cfg.models, "cebin_path") else "mock"),
            "JTrans": JTransAdapter(cfg.models.jtrans_path if hasattr(cfg.models, "jtrans_path") else "mock"),
            "CLAP": CLAPAdapter(cfg.models.clap_path if hasattr(cfg.models, "clap_path") else None),
            "PalmTree": PalmTreeAdapter(cfg.models.palmtree_path if hasattr(cfg.models, "palmtree_path") else "mock"),
        }

    def setup_models(self):
        for name, adapter in self.adapters.items():
            logger.info("Setting up model: %s", name)
            adapter.setup()

    def run_evaluation(self, model_names: list[str] | None = None):
        if model_names is None:
            model_names = list(self.adapters.keys())

        functions_dir = self.workdir / "functions"
        if not functions_dir.exists():
            logger.error("Functions directory not found. Run analyze first.")
            return

        # Task A: Obfuscated Query Search
        # We need to compare every obfuscated function against a gallery of originals
        
        # 1. Load all original function JSONs
        originals = []
        orig_dir = functions_dir / "original"
        if orig_dir.exists():
            for p in orig_dir.rglob("*.json"):
                with p.open() as f:
                    originals.append(json.load(f))
        
        if not originals:
            logger.warning("No original functions found for evaluation.")
            return

        for m_name in model_names:
            adapter = self.adapters[m_name]
            logger.info("Evaluating model: %s", m_name)
            
            # Embed gallery (originals)
            orig_embeddings = []
            for orig in tqdm(originals, desc=f"Embedding gallery ({m_name})"):
                res = adapter.embed(adapter.preprocess_function(orig))
                if res.success:
                    orig_embeddings.append({
                        "id": orig["function_id"],
                        "emb": res.embedding,
                        "meta": orig
                    })

            if not orig_embeddings:
                logger.warning("Failed to generate gallery embeddings for %s", m_name)
                continue

            # Embed queries (obfuscated)
            eval_results = []
            obs_dir = functions_dir / "obfuscated"
            if obs_dir.exists():
                obs_files = list(obs_dir.rglob("*.json"))
                for obs_p in tqdm(obs_files, desc=f"Evaluating queries ({m_name})"):
                    with obs_p.open() as f:
                        obs_func = json.load(f)
                    
                    res = adapter.embed(adapter.preprocess_function(obs_func))
                    if not res.success:
                        eval_results.append({
                            "model": m_name, "function": obs_func["function_id"],
                            "success": False, "failure_reason": res.failure_reason
                        })
                        continue

                    # Calculate similarities and Rank
                    scores = []
                    for item in orig_embeddings:
                        sim = adapter.similarity(res.embedding, item["emb"])
                        scores.append((sim, item["id"]))
                    
                    # Sort by similarity descending
                    scores.sort(key=lambda x: x[0], reverse=True)
                    
                    # Find rank of correct match
                    target_id = obs_func["function_id"]
                    rank = -1
                    target_sim = 0.0
                    for i, (sim, fid) in enumerate(scores):
                        if fid == target_id:
                            rank = i + 1
                            target_sim = sim
                            break
                    
                    eval_results.append({
                        "model": m_name,
                        "dataset": obs_func.get("dataset"),
                        "program": obs_func.get("program"),
                        "function": target_id,
                        "operator": obs_func.get("operator"),
                        "seed": obs_func.get("seed"),
                        "opt": obs_func.get("opt"),
                        "cs": target_sim,
                        "rank": rank,
                        "top1_hit": 1 if rank == 1 else 0,
                        "top5_hit": 1 if 1 <= rank <= 5 else 0,
                        "top10_hit": 1 if 1 <= rank <= 10 else 0,
                        "mrr": 1.0 / rank if rank > 0 else 0.0,
                        "success": True
                    })

            # Save detailed results
            df = pd.DataFrame(eval_results)
            df.to_csv(self.results_dir / f"model_eval_{m_name}.csv", index=False)
            
            # results/similarity_pairs_{model}.csv
            pairs_df = df[df["success"] == True][["function", "operator", "seed", "opt", "cs"]]
            pairs_df.to_csv(self.results_dir / f"similarity_pairs_{m_name}.csv", index=False)
            
            # results/topk_{model}.csv
            topk_df = df[df["success"] == True][["function", "rank", "top1_hit", "top5_hit", "top10_hit", "mrr"]]
            topk_df.to_csv(self.results_dir / f"topk_{m_name}.csv", index=False)

        # results/model_status.csv
        status_data = []
        for name, adapter in self.adapters.items():
            status_data.append({
                "model": name,
                "enabled": getattr(adapter, "enabled", False),
                "backend": getattr(adapter, "preprocessing_backend", "N/A"),
                "notes": getattr(adapter, "deviation_notes", "")
            })
        pd.DataFrame(status_data).to_csv(self.results_dir / "model_status.csv", index=False)
