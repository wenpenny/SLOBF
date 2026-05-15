<<<<<<< HEAD
"""SLOBF unified command-line interface."""
=======
"""SLOBF command-line interface."""
>>>>>>> master

from __future__ import annotations

import sys
from pathlib import Path

import click
<<<<<<< HEAD
=======
import pandas as pd
>>>>>>> master
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
<<<<<<< HEAD
    """SLOBF — Source-Level Obfuscation for Binary Function Similarity Analysis."""
=======
    """SLOBF - Source-Level Obfuscation for Binary Function Similarity Analysis."""
>>>>>>> master


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

<<<<<<< HEAD
def _init(config: str | None, **kwargs) -> tuple:
    """Load config, wire overrides, return (cfg, logger, exp_logger)."""
    overrides = {k: v for k, v in kwargs.items() if v is not None and v is not False}
    cfg = load_config(config, overrides)
    # Apply CLI booleans explicitly
=======
def _init(config: str | None, **kwargs):
    overrides = {k: v for k, v in kwargs.items() if v is not None and v is not False}
    cfg = load_config(config, overrides)
>>>>>>> master
    for flag in ("dry_run", "resume", "force", "verbose"):
        if kwargs.get(flag):
            setattr(cfg, flag, True)
    for int_key in ("threads", "seed"):
        if kwargs.get(int_key) is not None:
            setattr(cfg, int_key, kwargs[int_key])

<<<<<<< HEAD
    logger = get_logger("slobf", verbose=cfg.verbose)
    exp_logger = ExperimentLogger()
    meta = collect_run_metadata(seed=cfg.seed)
    exp_logger.log_run_start(meta)
    if cfg.dry_run:
=======
    logger = get_logger("slobf", verbose=getattr(cfg, "verbose", False))
    exp_logger = ExperimentLogger()
    meta = collect_run_metadata(seed=cfg.seed)
    exp_logger.log_run_start(meta)
    if getattr(cfg, "dry_run", False):
>>>>>>> master
        logger.info("[DRY RUN] No changes will be made.")
    return cfg, logger, exp_logger


<<<<<<< HEAD
def _not_implemented(cmd: str, cfg, logger) -> None:
    logger.warning("Command '%s' is not yet implemented (skeleton placeholder).", cmd)
    console.print(f"[yellow]⚠ [bold]{cmd}[/bold] — skeleton placeholder. Not implemented yet.[/yellow]")


=======
>>>>>>> master
# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

<<<<<<< HEAD
@main.command("prepare-dataset")
@click.option("--config", "-c", default=None, help="Path to datasets.yaml.")
@global_options
def prepare_dataset(config, **kwargs):
    """Download and prepare benchmark datasets."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    _not_implemented("prepare-dataset", cfg, logger)
    exp_logger.log_run_end({"status": "stub"})


@main.command("scan-functions")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@global_options
def scan_functions(config, **kwargs):
    """Scan source files and extract eligible C functions."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    
=======
@main.command("scan")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--dataset", default=None, help="Dataset name filter.")
@global_options
def scan(config, dataset, **kwargs):
    """Scan source files and extract eligible C functions."""
    cfg, logger, exp_logger = _init(config, **kwargs)

>>>>>>> master
    from slobf.dataset.manager import DatasetManager
    mgr = DatasetManager(cfg)
    df = mgr.scan_all()
    mgr.sample_functions(df)
<<<<<<< HEAD
    
    exp_logger.log_run_end({"status": "completed", "functions_found": len(df)})


@main.command("compile")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@global_options
def compile_cmd(config, **kwargs):
    """Compile original and obfuscated functions."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    from slobf.compiler.manager import CompilerManager
    mgr = CompilerManager(cfg)
    mgr.run_full_compilation(Path(cfg.paths.results_dir) / "obfuscation_summary.csv")
    exp_logger.log_run_end({"status": "completed"})

@main.command("analyze")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@global_options
def analyze_cmd(config, **kwargs):
    """Extract binary functions and calculate metrics."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    
    from slobf.binary.extractor import BinaryExtractor
    from slobf.metrics.calculator import MetricsCalculator
    
    results_dir = Path(cfg.paths.results_dir)
    workdir = Path(cfg.paths.workdir)
    
    # 1. Extraction
    extractor = BinaryExtractor()
    extractor.process_all(results_dir / "compile_results.csv", workdir / "functions")
    
    # 2. Metrics
    calc = MetricsCalculator(results_dir)
    calc.run_check()
    
    exp_logger.log_run_end({"status": "completed"})

@main.command("evaluate")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--model", default=None, help="Model(s) to evaluate, comma-separated.")
@global_options
def evaluate_cmd(config, model, **kwargs):
    """Run model evaluation on original and obfuscated functions."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    
    from slobf.models.manager import ModelManager
    mgr = ModelManager(cfg)
    mgr.setup_models()
    
    model_list = [m.strip() for m in model.split(",")] if model else None
    mgr.run_evaluation(model_list)
    
    exp_logger.log_run_end({"status": "completed"})
=======

    exp_logger.log_run_end({"status": "completed", "functions_found": len(df)})


@main.command("obfuscate")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--operator", default=None, help="Obfuscation operator (OPI/CFF/ER/DE/JCI/FS).")
@click.option("--function", "func_name", default=None, help="Target function name.")
@click.option("--source", "source_path", default=None, help="Path to source file.")
@click.option("--opt", default="O0", help="Optimisation level.")
@global_options
def obfuscate_cmd(config, operator, func_name, source_path, opt, **kwargs):
    """Apply an obfuscation operator to a function in-place and compile."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    if not operator or not func_name or not source_path:
        logger.error("--operator, --function, and --source are required.")
        return

    from slobf.obfuscators.manager import ObfuscationManager
    from slobf.compiler.manager import CompilerManager
    from slobf.parser.c_parser import CParser, FunctionInfo

    parser = CParser()
    func_info = FunctionInfo(name=func_name, source_file=source_path)

    mgr = ObfuscationManager(cfg)
    result = mgr.obfuscate_function_in_file(
        Path(source_path), func_info, operator,
        seed=cfg.seed, intensity=1.0,
    )

    if result and result.success:
        logger.info("Obfuscation successful. Lines: +%d / -%d",
                    result.inserted_lines, result.removed_lines)
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

>>>>>>> master

@main.command("rq1")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--seeds", default="0,1,2", help="Random seeds, comma-separated.")
@global_options
def rq1_cmd(config, seeds, **kwargs):
<<<<<<< HEAD
    """Run RQ1 experiment: impact of single operators on models."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    
    from slobf.experiments.rq1 import RQ1Runner
    from slobf.experiments.visualizer import plot_rq1_results
    
    seed_list = [int(s.strip()) for s in seeds.split(",")]
    
    runner = RQ1Runner(cfg)
    runner.run(seeds=seed_list)
    
    # Plot results
    plot_rq1_results(
        Path(cfg.paths.results_dir) / "rq1" / "single_operator_raw.csv",
        Path(cfg.paths.results_dir) / "rq1" / "plots"
    )
    
    exp_logger.log_run_end({"status": "completed"})

=======
    """Run RQ1: impact of single obfuscation operators."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    from slobf.experiments.rq1 import RQ1Runner

    seed_list = [int(s.strip()) for s in seeds.split(",")]
    runner = RQ1Runner(cfg)
    runner.run(seeds=seed_list)

    exp_logger.log_run_end({"status": "completed"})


>>>>>>> master
@main.command("rq2")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--train-steps", default=5000, help="Total RL training timesteps.")
@global_options
def rq2_cmd(config, train_steps, **kwargs):
<<<<<<< HEAD
    """Run RQ2 experiment: RL-guided obfuscation combination search."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    
    from slobf.experiments.rq2 import RQ2Runner
    runner = RQ2Runner(cfg)
    runner.run(train_timesteps=train_steps)
    
    exp_logger.log_run_end({"status": "completed"})

@main.command("rq3")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--functions", default=None, help="Path to functions CSV (default: selected_functions_rq1.csv).")
@global_options
def rq3_cmd(config, functions, **kwargs):
    """Run RQ3 experiment: impact of optimization levels."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    
    from slobf.experiments.rq3 import RQ3Runner
    if functions is None:
        functions = Path(cfg.paths.datasets_dir) / "selected_functions_rq1.csv"
    
    runner = RQ3Runner(cfg)
    runner.run(str(functions))
    
    exp_logger.log_run_end({"status": "completed"})

@main.command("run-tigress")
@click.option("--transform", required=True, help="Tigress transform (Flatten, Split, etc.)")
@click.option("--opt", default="O0", help="GCC optimization level.")
@click.option("--source", required=True, help="Source file path.")
@click.option("--func", required=True, help="Function name.")
@global_options
def run_tigress_cmd(transform, opt, source, func, **kwargs):
    """Run Tigress on a single function and compile."""
    cfg, logger, exp_logger = _init(None, **kwargs)
    from slobf.obfuscators.tigress import TigressAdapter
    
    adapter = TigressAdapter()
    if not adapter.check_installation():
        logger.error("Tigress not found. Run 'slobf install-tigress-helper' for info.")
        return

    output = Path("tigress_output.c")
    res = adapter.obfuscate(Path(source), output, func, transform)
    if res.success:
        logger.info("Tigress obfuscation successful: %s", output)
    else:
        logger.error("Tigress failed: %s", res.failure_reason)

@main.command("install-tigress-helper")
def install_tigress_helper():
    """Show help for installing Tigress."""
    from slobf.obfuscators.tigress import get_tigress_install_script
    print(get_tigress_install_script())

=======
    """Run RQ2: RL-guided obfuscation combination search."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    from slobf.experiments.rq2 import RQ2Runner
    runner = RQ2Runner(cfg)
    runner.run(train_timesteps=train_steps)

    exp_logger.log_run_end({"status": "completed"})


@main.command("rq3")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--functions", default=None, help="Path to functions CSV.")
@global_options
def rq3_cmd(config, functions, **kwargs):
    """Run RQ3: impact of compilation optimization levels."""
    cfg, logger, exp_logger = _init(config, **kwargs)

    from slobf.experiments.rq3 import RQ3Runner
    if functions is None:
        functions = Path(cfg.paths.results_dir) / "selected_functions_rq3.csv"

    runner = RQ3Runner(cfg)
    runner.run(str(functions))

    exp_logger.log_run_end({"status": "completed"})

>>>>>>> master

@main.command("sanity-check")
@click.option("--results", default="results", help="Results directory.")
def sanity_check_cmd(results):
    """Verify experimental results and generate paper artifacts."""
<<<<<<< HEAD
    res_dir = Path(results)
    errors = []
    
    # 1. Check directories
    for sub in ["rq1", "rq2", "rq3", "tables", "figures"]:
        if not (res_dir / sub).exists():
            errors.append(f"Missing directory: {sub}")
            
    # 2. Check key CSVs
    key_files = [
        "rq1/single_operator_raw.csv",
        "rq2/rl_eval_raw.csv",
        "rq3/optimization_raw.csv"
=======
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
>>>>>>> master
    ]
    for f in key_files:
        if not (res_dir / f).exists():
            errors.append(f"Missing results file: {f}")
<<<<<<< HEAD
            
    # 3. Generate Paper Tables
    from slobf.utils.paper_utils import generate_table_1_operators, generate_table_2_models, generate_table_3_datasets
=======

    from slobf.utils.paper_utils import (
        generate_table_1_operators,
        generate_table_2_models,
        generate_table_3_datasets,
    )
>>>>>>> master
    table_dir = res_dir / "tables"
    generate_table_1_operators(table_dir)
    generate_table_2_models(table_dir)
    generate_table_3_datasets(table_dir)
<<<<<<< HEAD
    
    # 4. Freeze Environment
    paper_dir = res_dir / "paper_ready"
    (paper_dir / "environment.txt").write_text(subprocess.check_output(["pip", "freeze"]).decode())
    (paper_dir / "random_seeds.txt").write_text("RQ1: [0, 1, 2]\nRQ2: 42\nRQ3: 0")
    
=======

    paper_dir = res_dir / "paper_ready"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "environment.txt").write_text(
        subprocess.check_output(["pip", "freeze"]).decode()
    )
    (paper_dir / "random_seeds.txt").write_text(
        "RQ1: [0, 1, 2]\nRQ2: 42\nRQ3: 0"
    )

>>>>>>> master
    if errors:
        click.echo("Sanity check FAILED:")
        for e in errors:
            click.echo(f"  - {e}")
    else:
<<<<<<< HEAD
        click.echo("Sanity check PASSED. Paper artifacts generated in results/tables/ and results/paper_ready/")

@main.command("obfuscate")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--operator", default=None, help="Obfuscation operator(s), comma-separated.")
@click.option("--opt", default=None, help="Optimisation level (O0/O1/O2/O3).")
@global_options
def obfuscate(config, operator, opt, **kwargs):
    """Apply source-level obfuscation operators to scanned functions."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    
    # Load selected functions (defaulting to RQ1 if not specified)
    results_dir = Path(cfg.paths.results_dir)
    selected_csv = results_dir / "selected_functions_rq1.csv"
    if not selected_csv.exists():
        logger.error("No selected functions found. Run scan-functions first.")
        return

    df = pd.read_csv(selected_csv)
    
    from slobf.obfuscators.manager import ObfuscationManager
    mgr = ObfuscationManager(cfg)
    
    op_list = [o.strip() for o in operator.split(",")] if operator else None
    mgr.run_obfuscation(df, op_list)
    
    exp_logger.log_run_end({"status": "completed"})


@main.command("compile")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--opt", default=None, help="Optimisation level (O0/O1/O2/O3).")
@global_options
def compile_(config, opt, **kwargs):
    """Compile obfuscated and baseline source files with GCC."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    if opt:
        cfg.compiler.opt_levels = [opt]
    logger.info("Opt levels: %s", cfg.compiler.opt_levels)
    _not_implemented("compile", cfg, logger)
    exp_logger.log_run_end({"status": "stub"})


@main.command("evaluate")
@click.option("--config", "-c", default=None, help="Path to config YAML.")
@click.option("--models", default=None, help="Model names, comma-separated (e.g. cebin,jtrans).")
@global_options
def evaluate(config, models, **kwargs):
    """Run binary similarity models and compute evaluation metrics."""
    cfg, logger, exp_logger = _init(config, **kwargs)
    model_list = [m.strip() for m in models.split(",")] if models else []
    logger.info("Models: %s", model_list)
    _not_implemented("evaluate", cfg, logger)
    exp_logger.log_run_end({"status": "stub"})


@main.command("run-rq1")
@click.option("--config", "-c", default=None, help="Path to experiments.yaml.")
@global_options
def run_rq1(config, **kwargs):
    """RQ1: How do individual obfuscation operators affect model performance?"""
    cfg, logger, exp_logger = _init(config, **kwargs)
    _not_implemented("run-rq1", cfg, logger)
    exp_logger.log_run_end({"status": "stub"})


@main.command("run-rq2")
@click.option("--config", "-c", default=None, help="Path to experiments.yaml.")
@global_options
def run_rq2(config, **kwargs):
    """RQ2: How do operator combinations affect model robustness?"""
    cfg, logger, exp_logger = _init(config, **kwargs)
    _not_implemented("run-rq2", cfg, logger)
    exp_logger.log_run_end({"status": "stub"})


@main.command("run-rq3")
@click.option("--config", "-c", default=None, help="Path to experiments.yaml.")
@global_options
def run_rq3(config, **kwargs):
    """RQ3: Can RL find operator combinations that maximise evasion with minimal overhead?"""
    cfg, logger, exp_logger = _init(config, **kwargs)
    _not_implemented("run-rq3", cfg, logger)
    exp_logger.log_run_end({"status": "stub"})


@main.command("report")
@click.option("--input", "input_dir", default="results", show_default=True, help="Results directory.")
@click.option("--output", "output_dir", default="results/report", show_default=True, help="Report output directory.")
@global_options
def report(input_dir, output_dir, **kwargs):
    """Generate CSV, JSON summary and plots from results directory."""
    cfg, logger, exp_logger = _init(None, **kwargs)
    logger.info("Input: %s | Output: %s", input_dir, output_dir)
    _not_implemented("report", cfg, logger)
    exp_logger.log_run_end({"status": "stub"})
=======
        click.echo("Sanity check PASSED.")
>>>>>>> master


if __name__ == "__main__":
    main()
