"""Logging utilities for SLOBF: human-readable + machine-readable (JSONL)."""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOGGERS: dict[str, logging.Logger] = {}


def _get_log_dir() -> Path:
    d = Path(os.environ.get("SLOBF_LOGS_DIR", "logs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_results_dir() -> Path:
    d = Path(os.environ.get("SLOBF_RESULTS_DIR", "results"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_cmd(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unknown"


def collect_run_metadata(seed: int = 0, operators: list[str] | None = None,
                         opt_levels: list[str] | None = None,
                         models: list[str] | None = None,
                         dataset_info: str | None = None) -> dict[str, Any]:
    """Collect reproducibility metadata for an experiment run."""
    git_hash = _run_cmd(["git", "rev-parse", "--short", "HEAD"])
    gcc_ver = _run_cmd(["gcc", "--version"]).splitlines()[0] if shutil.which("gcc") else "not found"
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_hash,
        "python_version": sys.version,
        "gcc_version": gcc_ver,
        "os": platform.platform(),
        "os_version": platform.version(),
        "seed": seed,
        "operators": operators or [],
        "opt_levels": opt_levels or [],
        "models": models or [],
        "dataset_version": dataset_info or "unknown",
    }


# ---------------------------------------------------------------------------
# Human-readable logger
# ---------------------------------------------------------------------------

def get_logger(name: str = "slobf", log_file: str | Path | None = None,
               verbose: bool = False) -> logging.Logger:
    """Return (and cache) a configured logger.

    Outputs to stderr + an optional file under logs/.
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    if log_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = _get_log_dir() / f"slobf_{ts}.log"
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    _LOGGERS[name] = logger
    return logger


# ---------------------------------------------------------------------------
# Machine-readable JSONL logger
# ---------------------------------------------------------------------------

class ExperimentLogger:
    """Append structured JSON events to a .jsonl file."""

    def __init__(self, run_id: str | None = None, results_dir: str | Path | None = None):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        rd = Path(results_dir) if results_dir else _get_results_dir()
        self._path = rd / f"run_{self.run_id}.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def log(self, event_type: str, **kwargs: Any) -> None:
        """Append a single event line."""
        record = {
            "run_id": self.run_id,
            "event": event_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        with self._path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def log_run_start(self, metadata: dict[str, Any]) -> None:
        self.log("run_start", **metadata)

    def log_function(self, func_name: str, source_file: str,
                     obfuscated: bool | None = None,
                     compiled: bool | None = None,
                     evaluated: bool | None = None,
                     failure_reason: str | None = None,
                     **kwargs: Any) -> None:
        self.log(
            "function",
            func_name=func_name,
            source_file=source_file,
            obfuscated=obfuscated,
            compiled=compiled,
            evaluated=evaluated,
            failure_reason=failure_reason,
            **kwargs,
        )

    def log_run_end(self, summary: dict[str, Any]) -> None:
        self.log("run_end", **summary)
