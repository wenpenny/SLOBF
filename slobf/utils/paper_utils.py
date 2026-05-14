"""Paper-ready table and LaTeX generation."""

from pathlib import Path

import pandas as pd


def export_table(df: pd.DataFrame, name: str, output_dir: Path):
    csv_path = output_dir / f"{name}.csv"
    tex_path = output_dir / f"{name}.tex"
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    with tex_path.open("w") as f:
        f.write(df.to_latex(index=False, caption=name.replace("_", " ").title()))


def generate_table_1_operators(output_dir: Path):
    data = [
        ["OPI", "Control Flow", "Insert opaque predicates (always-true conditions)", ">= 3 statements, no asm", "Increased basic blocks, CFG variation"],
        ["CFF", "Control Flow", "Flatten control flow via switch-loop dispatcher", ">= 5 statements, no goto/switch", "CFG complexity increase"],
        ["ER", "Data Flow", "Rewrite expressions to equivalent forms", "Any function", "Opcode diversity, instruction substitution"],
        ["DE", "Data Flow", "Encode constants and literals with XOR", ">= 1 statement", "Immediate value variation"],
        ["JCI", "Data Flow", "Insert junk/dead code blocks", ">= 2 statements", "Binary size growth, noisy instructions"],
        ["FS", "Structure", "Split function into caller + helper", ">= 8 statements", "Function count increase, inter-procedural edges"],
    ]
    df = pd.DataFrame(data, columns=["Operator", "Category", "AST-based transformation", "Eligibility", "Expected binary effect"])
    export_table(df, "table1_operators", output_dir)


def generate_table_2_models(output_dir: Path):
    data = [
        ["CEBin", "CFG + token sequence", "Graph neural network", "CS, Top-K"],
        ["JTrans", "Disassembly tokens", "Transformer (BERT-like)", "CS, MRR"],
        ["CLAP", "Assembly + source (contrastive)", "Transformer", "CS, Top-1"],
        ["PalmTree", "Instruction embedding", "BERT-like", "CS, Top-10"],
    ]
    df = pd.DataFrame(data, columns=["Model", "Input", "Architecture", "Metrics"])
    export_table(df, "table2_models", output_dir)


def generate_table_3_datasets(output_dir: Path):
    data = [
        ["Coreutils", "100+", "~300", "GCC 11.4", "O0–O3"],
        ["SQLite", "1", "~5000", "GCC 11.4", "O0–O3"],
        ["Zlib", "1", "~500", "GCC 11.4", "O0–O3"],
    ]
    df = pd.DataFrame(data, columns=["Dataset", "Programs", "Functions", "Compiler", "Opt levels"])
    export_table(df, "table3_datasets", output_dir)
