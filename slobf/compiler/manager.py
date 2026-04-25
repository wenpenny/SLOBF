"""Compilation management for original and obfuscated sources in SLOBF."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from slobf.config import SlobfConfig

logger = logging.getLogger(__name__)

@dataclass
class CompileResult:
    success: bool
    project: str
    function_id: str | None
    operator: str | None
    seed: int | None
    opt: str
    cmd: str
    stdout: str
    stderr: str
    return_code: int
    binary_path: str | None
    compile_time: float
    binary_size: int = 0

class CompilerManager:
    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.cc = cfg.compiler.cc
        self.build_dir = Path(cfg.paths.workdir) / "build"
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir = Path(cfg.paths.results_dir)

    def compile_original(self, project_name: str, source_path: Path, opt: str) -> CompileResult:
        """Compile an original project or file."""
        target_dir = self.build_dir / "original" / opt
        target_dir.mkdir(parents=True, exist_ok=True)
        
        binary_path = target_dir / f"{project_name}.elf"
        
        # Base command for single file compilation (common for experiments)
        cmd = [self.cc, f"-{opt}", "-g", "-fno-inline", str(source_path), "-o", str(binary_path)]
        if "O2" in opt or "O3" in opt:
            # For O2/O3, we allow inlining to see its effect, 
            # but user can configure this.
            cmd = [self.cc, f"-{opt}", "-g", str(source_path), "-o", str(binary_path)]

        start_time = time.time()
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=self.cfg.compiler.timeout_seconds)
            compile_time = time.time() - start_time
            success = res.returncode == 0
            
            binary_size = binary_path.stat().st_size if success and binary_path.exists() else 0
            
            return CompileResult(
                success=success, project=project_name, function_id=None, 
                operator=None, seed=None, opt=opt, cmd=" ".join(cmd),
                stdout=res.stdout, stderr=res.stderr, return_code=res.returncode,
                binary_path=str(binary_path) if success else None,
                compile_time=compile_time, binary_size=binary_size
            )
        except Exception as e:
            return CompileResult(
                success=False, project=project_name, function_id=None,
                operator=None, seed=None, opt=opt, cmd=" ".join(cmd),
                stdout="", stderr=str(e), return_code=-1,
                binary_path=None, compile_time=time.time() - start_time
            )

    def compile_obfuscated(self, obfuscation_result: dict, opt: str) -> CompileResult:
        """Compile a single obfuscated function source."""
        op = obfuscation_result["operator_name"]
        func_id = obfuscation_result["function_id"]
        seed = obfuscation_result["seed"]
        
        target_dir = self.build_dir / "obfuscated" / op / func_id / str(seed) / opt
        target_dir.mkdir(parents=True, exist_ok=True)
        
        source_path = target_dir / "obfuscated.c"
        source_path.write_text(obfuscation_result["changed_source"])
        
        binary_path = target_dir / "obfuscated.elf"
        
        cmd = [self.cc, f"-{opt}", "-g", "-fno-inline", str(source_path), "-o", str(binary_path)]
        if "O2" in opt or "O3" in opt:
            cmd = [self.cc, f"-{opt}", "-g", str(source_path), "-o", str(binary_path)]

        start_time = time.time()
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=self.cfg.compiler.timeout_seconds)
            compile_time = time.time() - start_time
            success = res.returncode == 0
            binary_size = binary_path.stat().st_size if success and binary_path.exists() else 0
            
            return CompileResult(
                success=success, project="obfuscated", function_id=func_id,
                operator=op, seed=seed, opt=opt, cmd=" ".join(cmd),
                stdout=res.stdout, stderr=res.stderr, return_code=res.returncode,
                binary_path=str(binary_path) if success else None,
                compile_time=compile_time, binary_size=binary_size
            )
        except Exception as e:
            return CompileResult(
                success=False, project="obfuscated", function_id=func_id,
                operator=op, seed=seed, opt=opt, cmd=" ".join(cmd),
                stdout="", stderr=str(e), return_code=-1,
                binary_path=None, compile_time=time.time() - start_time
            )

    def run_full_compilation(self, obfuscation_summary_path: Path):
        """Compile all original and obfuscated entries in parallel."""
        if not obfuscation_summary_path.exists():
            logger.error("Obfuscation summary not found: %s", obfuscation_summary_path)
            return

        summary = pd.read_csv(obfuscation_summary_path)
        
        from concurrent.futures import ThreadPoolExecutor
        tasks = []
        
        # 1. Originals
        unique_funcs = summary[["function_id", "source_file"]].drop_duplicates()
        with ThreadPoolExecutor(max_workers=self.cfg.threads) as executor:
            for _, row in unique_funcs.iterrows():
                for opt in self.cfg.compiler.opt_levels:
                    tasks.append(executor.submit(self.compile_original, row["function_id"], Path(row["source_file"]), opt))
            
            # 2. Obfuscated
            log_path = self.results_dir / "obfuscation_log.jsonl"
            if log_path.exists():
                with log_path.open() as f:
                    for line in f:
                        obs_res = json.loads(line)
                        if not obs_res["success"]: continue
                        for opt in self.cfg.compiler.opt_levels:
                            tasks.append(executor.submit(self.compile_obfuscated, obs_res, opt))

            results = [t.result().__dict__ for t in tqdm(tasks, desc="Compiling")]

        # Save all results
        df = pd.DataFrame(results)
        df.to_csv(self.results_dir / "compile_results.csv", index=False)
        logger.info("Compilation results saved to compile_results.csv")
