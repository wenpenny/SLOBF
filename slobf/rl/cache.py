"""Cache system for RQ2 to avoid redundant computations."""

import json
import hashlib
from pathlib import Path
from typing import Any, Optional

class ObfuscationCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.compilation_cache = cache_dir / "compilation.json"
        self.evaluation_cache = cache_dir / "evaluation.json"
        
        self._comp_data = self._load(self.compilation_cache)
        self._eval_data = self._load(self.evaluation_cache)

    def _load(self, path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except:
                return {}
        return {}

    def _save(self, path: Path, data: dict):
        path.write_text(json.dumps(data, indent=2))

    def get_compilation(self, func_hash: str, sequence: list[str]) -> Optional[dict]:
        key = f"{func_hash}_{'_'.join(sequence)}"
        return self._comp_data.get(key)

    def set_compilation(self, func_hash: str, sequence: list[str], result: dict):
        key = f"{func_hash}_{'_'.join(sequence)}"
        self._comp_data[key] = result
        self._save(self.compilation_cache, self._comp_data)

    def get_evaluation(self, bin_hash: str, model_name: str) -> Optional[dict]:
        key = f"{bin_hash}_{model_name}"
        return self._eval_data.get(key)

    def set_evaluation(self, bin_hash: str, model_name: str, result: dict):
        key = f"{bin_hash}_{model_name}"
        self._eval_data[key] = result
        self._save(self.evaluation_cache, self._eval_data)
