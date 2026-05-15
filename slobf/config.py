"""Configuration loading and merging for SLOBF."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PathsConfig:
    datasets_dir: str = "datasets"
    workdir: str = "workdir"
    results_dir: str = "results"
    logs_dir: str = "logs"


@dataclass
class CompilerConfig:
    cc: str = "gcc"
    opt_levels: list[str] = field(default_factory=lambda: ["O0", "O1", "O2", "O3"])
    extra_cflags: str = "-g"
    timeout_seconds: int = 120


@dataclass
class ObfuscationConfig:
    operators: list[str] = field(default_factory=lambda: ["OPI", "CFF", "ER", "DE", "JCI", "FS"])
    max_combo_depth: int = 3


@dataclass
class MetricsConfig:
    top_k: list[int] = field(default_factory=lambda: [1, 5, 10])
    similarity_threshold: float = 0.5
    semantic_test_cases: int = 50


@dataclass
class SlobfConfig:
    paths: PathsConfig = field(default_factory=PathsConfig)
    compiler: CompilerConfig = field(default_factory=CompilerConfig)
    obfuscation: ObfuscationConfig = field(default_factory=ObfuscationConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    seed: int = 42
    threads: int = 4
    dry_run: bool = False
    resume: bool = False
    force: bool = False
    verbose: bool = False
    _raw: dict = field(default_factory=dict, repr=False)


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    with p.open() as f:
        return yaml.safe_load(f) or {}


def load_config(
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> SlobfConfig:
    raw: dict = {}

    default_yaml = Path("configs/default.yaml")
    if default_yaml.exists():
        _deep_merge(raw, _load_yaml(default_yaml))

    if config_path is not None:
        _deep_merge(raw, _load_yaml(config_path))

    if overrides:
        _deep_merge(raw, overrides)

    cfg = SlobfConfig(_raw=copy.deepcopy(raw))

    if "paths" in raw:
        cfg.paths = PathsConfig(**{k: v for k, v in raw["paths"].items()
                                   if k in PathsConfig.__dataclass_fields__})
    if "compiler" in raw:
        cfg.compiler = CompilerConfig(**{k: v for k, v in raw["compiler"].items()
                                         if k in CompilerConfig.__dataclass_fields__})
    if "obfuscation" in raw:
        cfg.obfuscation = ObfuscationConfig(**{k: v for k, v in raw["obfuscation"].items()
                                               if k in ObfuscationConfig.__dataclass_fields__})
    if "metrics" in raw:
        cfg.metrics = MetricsConfig(**{k: v for k, v in raw["metrics"].items()
                                        if k in MetricsConfig.__dataclass_fields__})

    for attr in ("seed", "threads", "dry_run", "resume", "force", "verbose"):
        if attr in raw:
            setattr(cfg, attr, raw[attr])

    return cfg
