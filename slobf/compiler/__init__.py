"""compiler — GCC-based compilation pipeline.

Planned responsibilities:
  - Compile individual C files or function translation units
  - Support -O0 / -O1 / -O2 / -O3 / -Os / -Oz
  - Capture stdout, stderr, return code, and timing
  - Enforce per-function compilation timeout
  - Produce a CompilationResult with all artefact paths

Public API (to be implemented):
  GccCompiler(cc="gcc", cflags="", timeout=60)
  GccCompiler.compile(src_path, out_path, opt_level) -> CompilationResult
  CompilationResult: success, elapsed, stdout, stderr, binary_path
"""
