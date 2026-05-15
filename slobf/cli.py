"""SLOBF command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import pandas as pd
from rich.console import Console

from slobf import __version__
from slobf.config import load_config
from slobf.logging_utils import ExperimentLogger, collect_run_metadata, get_logger

console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Shared option decorators
# ---------------------------------------------------------------------------

_GLOBAL_OPTIONS = [
    click.option("--threads", default=4, show_default=True, help="Worker threads."),
    click.option("--seed", default=42, show_default=True, help="Random seed."),
    click.option("--dry-run", is_flag=True, help="Print actions without executing."),
    click.option("--resume", is_flag=True, help="Skip already-completed steps."),
    click.option("--force", is_flag=True, help="Overwrite existing outputs."),
    click.option("--verbose", is_flag=True, help="Debug-level logging."),
]


def global_options(func):
    for opt in reversed(_GLOBAL_OPTIONS):
        func = opt(func)
    return func


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(__version__, prog_name="slobf")
def main():
    """SLOBF - Source-Level Obfuscation for Binary Function Similarity Analysis."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init(config: str | None, **kwargs):
    overrides = {k: v for k, v in kwargs.items() if v is not None and v is not False}
    cfg = load_config(config, overrides)
    for flag in ("dry_run", "resume", "force", "verbose"):
        if kwargs.get(flag):
            setattr(cfg, flag, True)
    for int_key in ("threads", "seed"):
        if kwargs.get(int_key) is not None:
            setattr(cfg, int_key, kwargs[int_key])

    logger = get_logger("slobf", verbose=getattr(cfg, "verbose", False))
    exp_logger = ExperimentLogger()
    meta = collect_run_metadata(seed=cfg.seed)
    exp_logger.log_run_start(meta)
    if getattr(cfg, "dry_run", False):
        logger.info("[DRY RUN] No changes will be made.")
    return cfg, logger, exp_logger


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@main.command("scan")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--dataset", default=None, help="Dataset name filter.")
@global_options
def scan(config, dataset, **kwargs):
    """Scan source files and extract eligible C functions."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    from slobf.dataset.manager import DatasetManager
    mgr = DatasetManager(cfg)
    df = mgr.scan_all()
    mgr.sample_functions(df)

    exp_logger.log_run_end({"status": "completed", "functions_found": len(df)})


@main.command("obfuscate")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--operator", default=None, help="Obfuscation operator (OPI/CFF/ER/DE/JCI/FS).")
@click.option("--function", "func_name", default=None, help="Target function name.")
@click.option("--source", "source_path", default=None, help="Path to source file.")
@click.option("--output", "-o", "output_path", default=None, help="Output path for modified source (default: <source>.obf.c).")
@click.option("--opt", default="O0", help="Optimisation level.")
@global_options
def obfuscate_cmd(config, operator, func_name, source_path, output_path, opt, **kwargs):
    """Apply an obfuscation operator to a function and save the modified source."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    if not operator or not func_name or not source_path:
        logger.error("--operator, --function, and --source are required.")
        return

    from slobf.obfuscators.manager import ObfuscationManager
    from slobf.parser.c_parser import CParser

    parser = CParser()
    all_funcs = parser.parse_file(Path(source_path))
    func_info = next((f for f in all_funcs if f.name == func_name), None)
    if func_info is None:
        logger.error("Function '%s' not found in %s.", func_name, source_path)
        return

    mgr = ObfuscationManager(cfg)
    result = mgr.obfuscate_function_in_file(
        Path(source_path), func_info, operator,
        seed=cfg.seed, intensity=1.0,
    )

    if result and result.success:
        logger.info("Obfuscation successful. Lines: +%d / -%d",
                    result.inserted_lines, result.removed_lines)

        # Save modified source
        out_path = Path(output_path) if output_path else Path(source_path).with_suffix(".obf.c")
        out_path.write_text(result.changed_source, encoding="utf-8")
        logger.info("Obfuscated source saved to: %s", out_path)

        # Print diff summary
        if result.diff:
            logger.info("Diff:\n%s", result.diff[:2000])
    else:
        logger.error("Obfuscation failed: %s",
                     result.reason_if_failed if result else "unknown operator")

    exp_logger.log_run_end({"status": "completed" if result and result.success else "failed"})


@main.command("compile")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--program", "program_dir", default=None, help="Path to program source directory.")
@click.option("--opt", default="O0", help="Optimisation level.")
@click.option("--modified-file", default=None, help="Path to modified source file.")
@click.option("--modified-content-file", default=None, help="Path to file containing modified content.")
@global_options
def compile_cmd(config, program_dir, opt, modified_file, modified_content_file, **kwargs):
    """Compile a full C program (optionally with modified source)."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    if not program_dir:
        logger.error("--program is required.")
        return

    from slobf.compiler.manager import CompilerManager

    modified_content = None
    if modified_content_file:
        modified_content = Path(modified_content_file).read_text()

    mgr = CompilerManager(cfg)
    result = mgr.compile_program(
        Path(program_dir), "output", opt,
        modified_file=Path(modified_file) if modified_file else None,
        modified_content=modified_content,
    )

    if result.success:
        logger.info("Compilation successful: %s", result.binary_path)
    else:
        logger.error("Compilation failed: %s", result.stderr[:500])

    exp_logger.log_run_end({"status": "completed" if result.success else "failed"})


@main.command("extract")
@click.option("--binary", "binary_path", default=None, help="Path to ELF binary.")
@click.option("--function", "func_name", default=None, help="Function name to extract.")
@click.option("--output", "output_dir", default="results/functions", help="Output directory.")
@global_options
def extract_cmd(binary_path, func_name, output_dir, **kwargs):
    """Extract a function from an ELF binary."""
    cfg, logger, exp_logger = _init(None, **kwargs)

    if not binary_path or not func_name:
        logger.error("--binary and --function are required.")
        return

    from slobf.binary.extractor import BinaryExtractor

    extractor = BinaryExtractor()
    bf = extractor.extract_and_save(Path(binary_path), func_name, Path(output_dir))
    if bf:
        logger.info("Extracted %s: %d instructions", bf.name, bf.instruction_count)
    else:
        logger.warning("Extraction failed — function may have been inlined.")

    exp_logger.log_run_end({"status": "completed" if bf else "failed"})


@main.command("verify")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--original", default=None, help="Path to original source file.")
@click.option("--obfuscated", default=None, help="Path to obfuscated source file.")
@click.option("--function", "func_name", default=None, help="Function name.")
@global_options
def verify_cmd(config, original, obfuscated, func_name, **kwargs):
    """Verify semantic equivalence between original and obfuscated function."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    if not original or not obfuscated or not func_name:
        logger.error("--original, --obfuscated, and --function are required.")
        return

    from slobf.parser.c_parser import FunctionInfo
    from slobf.metrics.semantic import SemanticVerifier

    func_info = FunctionInfo(name=func_name)
    verifier = SemanticVerifier(cc=cfg.compiler.cc, num_cases=cfg.metrics.semantic_test_cases)
    result = verifier.verify(Path(original), Path(obfuscated), func_info, seed=cfg.seed)

    if result.get("passed"):
        logger.info("Semantic equivalence VERIFIED (%d cases)", result["total_cases"])
    else:
        logger.error("Semantic check FAILED: %s", result.get("error", "output mismatch"))
        mismatches = result.get("mismatches", [])
        for m in mismatches[:5]:
            logger.error("  Case %d: orig=%s  obf=%s",
                         m["case"], m["original"].strip(), m["obfuscated"].strip())

    exp_logger.log_run_end({"status": "completed"})


@main.command("rq1")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--seeds", default="0,1,2", help="Random seeds, comma-separated.")
@global_options
def rq1_cmd(config, seeds, **kwargs):
    """Run RQ1: impact of single obfuscation operators."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    from slobf.experiments.rq1 import RQ1Runner

    seed_list = [int(s.strip()) for s in seeds.split(",")]
    runner = RQ1Runner(cfg)
    runner.run(seeds=seed_list)

    exp_logger.log_run_end({"status": "completed"})


@main.command("rq2")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--train-steps", default=5000, help="Total RL training timesteps.")
@global_options
def rq2_cmd(config, train_steps, **kwargs):
    """Run RQ2: RL-guided obfuscation combination search."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    from slobf.experiments.rq2 import RQ2Runner
    runner = RQ2Runner(cfg)
    runner.run(train_timesteps=train_steps)

    exp_logger.log_run_end({"status": "completed"})


@main.command("rq3")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--functions", default=None, help="Path to functions CSV (default: selected_functions_test.csv).")
@global_options
def rq3_cmd(config, functions, **kwargs):
    """Run RQ3: impact of compilation optimization levels."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    from slobf.experiments.rq3 import RQ3Runner
    runner = RQ3Runner(cfg)
    runner.run(functions)

    exp_logger.log_run_end({"status": "completed"})


@main.command("sanity-check")
@click.option("--results", default="results", help="Results directory.")
def sanity_check_cmd(results):
    """Verify experimental results and generate paper artifacts."""
    import subprocess
    res_dir = Path(results)
    errors = []

    for sub in ["rq1", "rq2", "rq3", "tables", "figures"]:
        if not (res_dir / sub).exists():
            errors.append(f"Missing directory: {sub}")

    key_files = [
        "rq1/single_operator_raw.csv",
        "rq2/rl_eval_raw.csv",
        "rq3/optimization_raw.csv",
    ]
    for f in key_files:
        if not (res_dir / f).exists():
            errors.append(f"Missing results file: {f}")

    from slobf.utils.paper_utils import (
        generate_table_1_operators,
        generate_table_2_models,
        generate_table_3_datasets,
    )
    table_dir = res_dir / "tables"
    generate_table_1_operators(table_dir)
    generate_table_2_models(table_dir)
    generate_table_3_datasets(table_dir)

    paper_dir = res_dir / "paper_ready"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "environment.txt").write_text(
        subprocess.check_output(["pip", "freeze"]).decode()
    )
    (paper_dir / "random_seeds.txt").write_text(
        "RQ1: [0, 1, 2]\nRQ2: 42\nRQ3: 0"
    )

    if errors:
        click.echo("Sanity check FAILED:")
        for e in errors:
            click.echo(f"  - {e}")
    else:
        click.echo("Sanity check PASSED.")


if __name__ == "__main__":
    main()
