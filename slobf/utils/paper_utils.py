"""Utility for generating paper-ready tables and LaTeX code."""

import pandas as pd
from pathlib import Path

def export_table(df: pd.DataFrame, name: str, output_dir: Path):
    """Save DataFrame as CSV and LaTeX."""
    csv_path = output_dir / f"{name}.csv"
    tex_path = output_dir / f"{name}.tex"
    
    df.to_csv(csv_path, index=False)
    
    # Generate simple LaTeX table
    with open(tex_path, "w") as f:
        f.write(df.to_latex(index=False, caption=name.replace("_", " ").title()))

def generate_table_1_operators(output_dir: Path):
    data = [
        ["OPI", "Arithmetic", "Replace constants with opaque expressions", "Contains integers", "Instruction variety"],
        ["CFF", "Control Flow", "Flatten control flow via switch-loop", "Branching logic", "Complexity increase"],
        ["ER", "Data Flow", "Add redundant code and dummy variables", "Variable usage", "Data dependency"],
        ["DE", "Arithmetic", "Dead code injection", "Always", "Binary size growth"],
        ["JCI", "Control Flow", "Jump condition inversion", "Conditional branches", "CFG variation"],
        ["FS", "Structure", "Function splitting", "LOC > 10", "Function count increase"],
    ]
    df = pd.DataFrame(data, columns=["Operator", "Category", "Source-level transformation", "Eligibility rule", "Expected binary effect"])
    export_table(df, "table1_operators", output_dir)

def generate_table_2_models(output_dir: Path):
    data = [
        ["CEBin", "Token sequence", "Open-source (PyTorch)", "Similarity Score", "CS, Top-K", "Official implementation used"],
        ["JTrans", "Disassembly tokens", "IDA Pro (replaced with Capstone)", "Embedding", "CS, MRR", "Adapted to open-source extractor"],
        ["CLAP", "Contrastive Learning", "Transformer-based", "Embedding", "CS, Top-1", "Evaluation might be unstable"],
        ["PalmTree", "Instruction sequence", "BERT-like", "Vector", "CS, Top-10", "Pre-trained weights used"],
    ]
    df = pd.DataFrame(data, columns=["Model", "Input representation", "Preprocessing backend", "Output", "Used metrics", "Notes"])
    export_table(df, "table2_models", output_dir)

def generate_table_3_datasets(output_dir: Path):
    data = [
        ["Coreutils", "100+", "300+", "10,000+", "5,000+", "1,000", "GCC 11.4", "O0-O3"],
        ["SQLite", "1", "1", "5,000+", "2,000+", "500", "GCC 11.4", "O0-O3"],
        ["Zlib", "1", "10+", "500+", "200+", "100", "GCC 11.4", "O0-O3"],
    ]
    df = pd.DataFrame(data, columns=["Dataset", "Programs", "Source files", "Scanned functions", "Eligible functions", "Selected functions", "Compiler", "Optimization levels"])
    export_table(df, "table3_datasets", output_dir)
