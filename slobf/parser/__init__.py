"""parser — C source-code parsing and function extraction.

Planned responsibilities:
  - Parse C source files using libclang or tree-sitter
  - Extract function boundaries (start/end line, signature, body)
  - Detect inline, static, and macro-heavy functions
  - Build a FunctionRecord dataclass with metadata

Public API (to be implemented):
  CParser.parse_file(path) -> list[FunctionRecord]
  FunctionRecord: name, file, start_line, end_line, body, signature
"""
