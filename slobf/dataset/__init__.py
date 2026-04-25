"""dataset — Dataset loading, filtering, and management.

Planned responsibilities:
  - Download / verify benchmark datasets (XO, BinaryCorp, Trex-dataset, etc.)
  - Iterate source files and yield (file_path, function_name) pairs
  - Maintain a SQLite or JSON function registry
  - Filter functions by size, complexity, and language constraints

Public API (to be implemented):
  DatasetManager.prepare(config) -> None
  DatasetManager.list_functions() -> list[FunctionRecord]
"""
