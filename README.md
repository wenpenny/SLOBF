# SLOBF — Source-Level Obfuscation for Binary Function Similarity

Source-level obfuscation framework for evaluating the resilience of deep
learning-based binary similarity models.  Obfuscation is applied at function
granularity via tree-sitter AST transformations; all six operators are
semantics-preserving by construction.

## Operators

| Operator | Mechanism |
|----------|-----------|
| **OPI** — Opaque Predicate Insertion | Wraps statements in if-else guarded by always-true mathematical identities |
| **CFF** — Control Flow Flattening | Decomposes control flow into a while-switch dispatcher |
| **ER**  — Expression Rewriting | Replaces arithmetic/logical expressions with algebraically equivalent forms |
| **DE**  — Data Encoding | Encodes integer constants and string literals with self-inverse XOR layers |
| **JCI** — Junk Code Insertion | Inserts dead code blocks (volatile-qualified to resist compiler elimination) |
| **FS**  — Function Splitting | Splits a function body into a caller stub and a static helper function |

## Supported Binary Similarity Models

| Model | Venue | Architecture |
|-------|-------|-------------|
| jTrans   | ISSTA 2022 | BERT + control-flow graph |
| PalmTree | CCS 2021   | BERT for assembly instructions |
| CLAP     | ISSTA 2024 | Contrastive assembly–text pretraining |
| CEBin    | ISSTA 2024 | RoBERTa + GNN with retrieval augmentation |

## Requirements

- Python 3.10+
- GCC 11.4+
- Ubuntu 22.04 (or compatible Linux distribution)

## Installation

```bash
git clone https://github.com/wenpenny/SLOBF.git
cd SLOBF
bash scripts/setup_env.sh
source venv/bin/activate
bash scripts/download_datasets.sh
```

The setup script creates a virtual environment and installs all dependencies.
The download script fetches four GNU utility packages (coreutils 9.1, binutils
2.41, diffutils 3.10, findutils 4.9.0) used as the evaluation dataset.

Third-party model weights must be placed under `models/{CEBin,CLAP,PalmTree,jTrans}/`
before running experiments.  See `models/` directory structure in the repository
for the expected layout.

## Experiments

The framework evaluates three research questions:

| RQ | Question | Entry Point |
|----|----------|-------------|
| RQ1 | Impact of individual operators on model accuracy | `slobf rq1` |
| RQ2 | RL-guided cost-aware operator combination search | `slobf rq2` |
| RQ3 | Effect of compiler optimisation levels (O0–O3) | `slobf rq3` |

All results are written to `results/` with CSV tables, LaTeX tables, and
publication-ready figures.

### Reproducibility

All random seeds are fixed.  Dataset splits are deterministic (sorted by
function name, no random shuffling).  The configuration files under `configs/`
document every tunable parameter.

## Package Structure

```
slobf/
├── obfuscators/    # AST-based obfuscation operators (tree-sitter C)
├── parser/         # C source parser and function metadata extraction
├── compiler/       # Full-program GCC compilation with incremental rebuild
├── binary/         # ELF function extraction via pyelftools + Capstone
├── models/         # Adapters for four binary similarity models
├── rl/             # PPO-based operator sequence optimisation (Gymnasium)
├── experiments/    # RQ1 / RQ2 / RQ3 experiment runners
├── metrics/        # Similarity metrics, retrieval evaluation, semantic verifier
├── dataset/        # Function scanning, screening, and stratified splitting
└── utils/          # LaTeX table and figure generation
```

## License

MIT
