"""binary — Binary analysis and feature extraction.

Planned responsibilities:
  - Disassemble ELF binaries with objdump / capstone
  - Extract per-function byte sequences, CFG, call graph
  - Compute binary size, instruction count, cyclomatic complexity
  - Produce BinaryFunction objects consumed by model adapters

Public API (to be implemented):
  BinaryExtractor.extract(binary_path) -> list[BinaryFunction]
  BinaryFunction: name, bytes, instructions, cfg_edges, size_bytes
"""
