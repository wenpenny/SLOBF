# SLOBF — Source-Level Obfuscation for Binary Function Similarity Analysis

Function-level source code obfuscation framework for evaluating the resilience of deep learning-based binary similarity models. Built on tree-sitter AST transformation, all operators are semantics-preserving.

## Operators

| Operator | Description |
|----------|------------|
| **OPI** — Opaque Predicate Insertion | Wraps statements in if-else guarded by always-true mathematical identities |
| **CFF** — Control Flow Flattening | Decomposes control flow into a while-switch dispatcher |
| **ER** — Expression Rewriting | Replaces arithmetic/logical expressions with algebraically equivalent forms |
| **DE** — Data Encoding | Encodes integer constants and string literals with self-inverse XOR layers |
| **JCI** — Junk Code Insertion | Inserts dead code blocks with no side effects |
| **FS** — Function Splitting | Splits a function into caller + static helper |

## Installation

```bash
git clone https://github.com/wenpenny/SLOBF.git
cd SLOBF
bash scripts/setup_env.sh
source venv/bin/activate
bash scripts/download_datasets.sh
```

Requirements: GCC 11.4+, Python 3.10+, Ubuntu 22.04 (or Windows with MinGW-w64).

## Quick Start

```bash
# Scan and extract functions from dataset
slobf scan

# Apply an operator to a single function
slobf obfuscate --operator OPI --function func_name --source file.c --output result.c

# Run all experiments
bash scripts/run_all.sh
```

## Experiments

Three research questions:

| RQ | Question | Command |
|----|----------|---------|
| RQ1 | Impact of individual operators on model accuracy | `slobf rq1` |
| RQ2 | RL-guided cost-aware operator combination search | `slobf rq2` |
| RQ3 | Effect of compiler optimization levels (O0–O3) | `slobf rq3` |

Results are saved under `results/` with LaTeX tables and figures.

## Project Structure

```
slobf/
├── obfuscators/    # AST-based obfuscation operators
├── parser/         # tree-sitter C parser
├── compiler/       # GCC compilation manager
├── binary/         # ELF function extraction
├── models/         # Binary similarity model adapters
├── rl/             # PPO-based sequence optimisation
├── experiments/    # RQ1/RQ2/RQ3 runners
├── metrics/        # Similarity metrics and semantic verifier
└── dataset/        # Dataset scanning and function screening
```

## Extending

- **New operator**: Subclass `BaseObfuscator` in `slobf/obfuscators/` and register in `ObfuscationManager`
- **New model**: Implement `ModelAdapter` protocol in `slobf/models/`

## License

MIT
