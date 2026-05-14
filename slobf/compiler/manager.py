"""Full-program compilation manager for SLOBF.

Rather than extracting and compiling single functions, this module:
1. Copies an entire program source tree into a workspace.
2. Applies obfuscation to the target function *in-place* in the copied source.
3. Compiles the whole program (all .c files).
4. The resulting binary preserves realistic compiler behaviour (inlining, inter-procedural
   optimisation) for RQ3 validity.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from slobf.config import SlobfConfig

logger = logging.getLogger(__name__)


@dataclass
class CompileResult:
    success: bool
    program: str
    function_name: str
    operator: str | None
    seed: int | None
    opt: str
    cmd: str
    binary_path: str | None
    compile_time: float
    binary_size: int = 0
    stdout: str = ""
    stderr: str = ""


class CompilerManager:
    """Compiles entire C programs after in-place function obfuscation."""

    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.cc = cfg.compiler.cc
        self.workdir = Path(cfg.paths.workdir)
        self.build_dir = self.workdir / "build"
        self.build_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile_program(
        self,
        program_dir: Path,
        output_name: str,
        opt: str = "O0",
        extra_flags: str | None = None,
        modified_file: Path | None = None,
        modified_content: str | None = None,
    ) -> CompileResult:
        """Compile an entire program.

        If *modified_file* and *modified_content* are given, the modified source is
        written to a workspace copy before compilation so the original is never touched.
        """
        workspace = self.build_dir / output_name / opt
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(str(program_dir), str(workspace),
                        dirs_exist_ok=True, symlinks=True)

        # Apply source modification in the workspace copy
        if modified_file is not None and modified_content is not None:
            rel = modified_file.relative_to(program_dir)
            target = workspace / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(modified_content, encoding="utf-8")

        # Build command: compile all .c files together
        c_files = list(workspace.rglob("*.c"))
        if not c_files:
            return self._fail(output_name, "", opt, "no .c files found")

        binary_path = workspace / f"{output_name}.elf"
        flags = extra_flags or self.cfg.compiler.extra_cflags

        cmd = [
            self.cc, f"-{opt}", flags,
            "-o", str(binary_path),
        ] + [str(f) for f in sorted(c_files)]

        return self._run_cmd(cmd, output_name, "", opt, binary_path)

    def compile_baseline(
        self, program_dir: Path, program_name: str, opt: str = "O0"
    ) -> CompileResult:
        """Compile unmodified program (baseline)."""
        return self.compile_program(program_dir, f"{program_name}_baseline", opt)

    def compile_obfuscated(
        self,
        program_dir: Path,
        program_name: str,
        func_name: str,
        operator: str,
        seed: int,
        opt: str,
        modified_file: Path,
        modified_source: str,
    ) -> CompileResult:
        """Compile program with an obfuscated function."""
        tag = f"{program_name}_{func_name}_{operator}_s{seed}"
        return self.compile_program(
            program_dir, tag, opt,
            modified_file=modified_file, modified_content=modified_source,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_cmd(self, cmd: list[str], program: str, func_name: str,
                 opt: str, binary_path: Path) -> CompileResult:
        logger.debug("Compile: %s", " ".join(str(x) for x in cmd))
        start = time.time()
        try:
            proc = subprocess.run(
                [str(x) for x in cmd],
                capture_output=True, text=True,
                timeout=self.cfg.compiler.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False, program=program, function_name=func_name,
                operator=None, seed=None, opt=opt,
                cmd=" ".join(str(x) for x in cmd),
                binary_path=None, compile_time=self.cfg.compiler.timeout_seconds,
                stderr="timeout",
            )

        elapsed = time.time() - start
        ok = proc.returncode == 0 and binary_path.exists()
        return CompileResult(
            success=ok,
            program=program,
            function_name=func_name,
            operator=None,
            seed=None,
            opt=opt,
            cmd=" ".join(str(x) for x in cmd),
            binary_path=str(binary_path) if ok else None,
            compile_time=elapsed,
            binary_size=binary_path.stat().st_size if ok else 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def _fail(self, program: str, func_name: str, opt: str, reason: str) -> CompileResult:
        return CompileResult(
            success=False, program=program, function_name=func_name,
            operator=None, seed=None, opt=opt, cmd="",
            binary_path=None, compile_time=0, stderr=reason,
        )
