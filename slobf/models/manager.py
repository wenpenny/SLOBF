"""Manager for running model evaluations in SLOBF."""

from __future__ import annotations

import logging
from pathlib import Path

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


_MODEL_MAP = {
    "CEBin": CEBinAdapter,
    "JTrans": JTransAdapter,
    "CLAP": CLAPAdapter,
    "PalmTree": PalmTreeAdapter,
}


class ModelManager:
    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.adapters: dict[str, ModelAdapter] = {}

        # Use checkpoints from config if available, otherwise mock
        model_paths = cfg._raw.get("models", {})

        for name, cls in _MODEL_MAP.items():
            if name == "CLAP":
                self.adapters[name] = cls()
            else:
                path = model_paths.get(name.lower() + "_path", None)
                self.adapters[name] = cls(model_path=path)

    def setup_models(self):
        for name, adapter in self.adapters.items():
            try:
                adapter.setup()
                logger.info("Model %s ready: %s", name, getattr(adapter, "enabled", "unknown"))
            except Exception as e:
                logger.warning("Model %s setup failed: %s", name, e)

    def run_evaluation(self, model_names: list[str] | None = None):
        """Evaluate all models on original vs obfuscated function pairs.

        Expects function JSONs under workdir/functions/original/ and
        workdir/functions/obfuscated/.
        """
        if model_names is None:
            model_names = list(self.adapters.keys())

        functions_dir = Path(self.cfg.paths.workdir) / "functions"
        if not functions_dir.exists():
            logger.error("Functions directory not found. Run extract first.")
            return

        # Load originals
        originals = self._load_functions(functions_dir / "original")
        obfuscated = self._load_functions(functions_dir / "obfuscated")

        if not originals or not obfuscated:
            logger.warning("Missing function JSONs for evaluation.")
            return

        for m_name in model_names:
            adapter = self.adapters[m_name]
            logger.info("Evaluating %s...", m_name)

            # Embed gallery
            gallery = {}
            for orig in tqdm(originals, desc=f"Embedding ({m_name})"):
                inp = adapter.preprocess_function(orig)
                result = adapter.embed(inp)
                if result.success:
                    gallery[orig["name"]] = {
                        "embedding": result.embedding,
                        "meta": orig,
                    }

            # Embed queries and compute similarity
            eval_rows = []
            for obs in tqdm(obfuscated, desc=f"Search ({m_name})"):
                inp = adapter.preprocess_function(obs)
                result = adapter.embed(inp)
                if not result.success:
                    continue

                target_id = obs.get("name", "")
                scores = []
                for gid, gdata in gallery.items():
                    sim = adapter.similarity(result.embedding, gdata["embedding"])
                    scores.append((sim, gid))

                scores.sort(key=lambda x: x[0], reverse=True)
                rank = -1
                target_sim = 0.0
                for i, (sim, fid) in enumerate(scores):
                    if fid == target_id:
                        rank = i + 1
                        target_sim = sim
                        break

                eval_rows.append({
                    "model": m_name,
                    "function": target_id,
                    "operator": obs.get("operator"),
                    "seed": obs.get("seed"),
                    "opt": obs.get("opt"),
                    "cs": target_sim,
                    "rank": rank,
                    "top1_hit": 1 if rank == 1 else 0,
                    "top5_hit": 1 if 1 <= rank <= 5 else 0,
                    "top10_hit": 1 if 1 <= rank <= 10 else 0,
                    "mrr": 1.0 / rank if rank > 0 else 0.0,
                })

            df = pd.DataFrame(eval_rows)
            df.to_csv(
                Path(self.cfg.paths.results_dir) / f"model_eval_{m_name}.csv",
                index=False,
            )

    @staticmethod
    def _load_functions(directory: Path) -> list[dict]:
        if not directory.exists():
            return []
        import json
        funcs = []
        for p in sorted(directory.rglob("*.json")):
            try:
                with p.open() as f:
                    funcs.append(json.load(f))
            except Exception:
                pass
        return funcs
