"""Full-program compilation manager for SLOBF.

Strategy: copy the pre-built program directory to a workspace, apply the
obfuscated .c, run make incrementally, then locate the binary containing
the target function for extraction.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from slobf.config import SlobfConfig

logger = logging.getLogger(__name__)

_ELFTools = None  # lazy import


def _get_elftools():
    global _ELFTools
    if _ELFTools is None:
        from elftools.elf.elffile import ELFFile
        _ELFTools = ELFFile
    return _ELFTools


@dataclass
class CompileResult:
    success: bool
    program: str
    function_name: str
    operator: str | None
    seed: int | None
    opt: str
    cmd: str
    binary_path: str | None       # path to the ELF binary containing target function
    workspace_path: str | None    # path to the workspace directory (for cleanup)
    compile_time: float
    binary_size: int = 0
    stdout: str = ""
    stderr: str = ""


class CompilerManager:
    """Compiles C programs with optionally-obfuscated source files.

    Copies the pre-built program tree to a workspace so make can run
    incrementally — only the changed .c is recompiled, then binaries
    are re-linked.  After make, locates the binary containing the
    target function for extraction.
    """

    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.cc = cfg.compiler.cc
        self.workdir = Path(cfg.paths.workdir)
        self.build_dir = self.workdir / "build"
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self._baseline_workspace: Path | None = None

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
        function_name: str = "",
    ) -> CompileResult:
        workspace = self.build_dir / output_name / opt
        if workspace.exists():
            shutil.rmtree(workspace)

        shutil.copytree(
            str(program_dir), str(workspace),
            symlinks=True, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
        )

        if modified_file is not None and modified_content is not None:
            rel = modified_file.resolve().relative_to(program_dir.resolve())
            target = workspace / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(modified_content, encoding="utf-8")

        self._touch_generated(workspace)
        self._fix_permissions(workspace)

        nproc = os.cpu_count() or 4
        flags = extra_flags or self.cfg.compiler.extra_cflags
        cmd = [
            "make", f"-j{nproc}",
            "AUTOCONF=true", "AUTOHEADER=true", "ACLOCAL=true", "AUTOMAKE=true",
            f"CFLAGS=-{opt} {flags}",
        ]
        t_start = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.cfg.compiler.timeout_seconds,
                cwd=str(workspace),
            )
        except subprocess.TimeoutExpired:
            return self._fail(output_name, function_name, opt, "make timeout")

        elapsed = time.time() - t_start
        if proc.returncode != 0:
            return CompileResult(
                success=False, program=output_name, function_name=function_name,
                operator=None, seed=None, opt=opt,
                cmd=f"make -j{nproc} CFLAGS=-{opt}",
                binary_path=None, workspace_path=str(workspace),
                compile_time=elapsed, stderr=proc.stderr[:1000],
            )

        # Locate the binary containing the target function
        binary_path = None
        if function_name:
            binary_path = self._find_function_binary(workspace, function_name)

        bsize = 0
        if binary_path:
            bsize = Path(binary_path).stat().st_size

        return CompileResult(
            success=True,
            program=output_name,
            function_name=function_name,
            operator=None,
            seed=None,
            opt=opt,
            cmd=f"make -j{nproc} CFLAGS=-{opt}",
            binary_path=binary_path,
            workspace_path=str(workspace),
            compile_time=elapsed,
            binary_size=bsize,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def compile_baseline(
        self, program_dir: Path, program_name: str,
        opt: str = "O0", function_name: str = "",
    ) -> CompileResult:
        # Reuse workspace if already built for this program+opt
        tag = f"{program_name}_baseline"
        existing = self.build_dir / tag / opt
        if existing.exists():
            # Verify workspace is intact (not a leftover from a failed build)
            makefile = existing / "Makefile"
            if makefile.exists() and any(existing.rglob("*.o")):
                return CompileResult(
                    success=True, program=tag, function_name=function_name,
                    operator=None, seed=None, opt=opt,
                    cmd="(cached)",
                    binary_path=self._find_function_binary(existing, function_name),
                    workspace_path=str(existing),
                    compile_time=0,
                )
            logger.debug("Baseline cache miss: workspace incomplete, rebuilding")
        return self.compile_program(
            program_dir, tag, opt, function_name=function_name,
        )

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
        """Incremental compile on top of the baseline workspace.

        Instead of copying the entire program tree and rebuilding from scratch
        (which was O(project-size) rmtree + copytree per variant), this
        reuses the baseline workspace: only the obfuscated .c is swapped in,
        make rebuilds incrementally, and the binary is extracted.
        """
        # Ensure the baseline workspace exists and is built
        baseline_tag = f"{program_name}_baseline"
        workspace = self.build_dir / baseline_tag / opt
        bl = self.compile_baseline(program_dir, program_name, opt, func_name)
        if not bl.success or not workspace.exists():
            return CompileResult(
                success=False, program=program_name,
                function_name=func_name, operator=operator, seed=seed,
                opt=opt, cmd="", binary_path=None, workspace_path=None,
                compile_time=0,
                stderr="baseline build failed — cannot compile obfuscated",
            )

        # Write the obfuscated source file (overwrites baseline copy)
        rel = modified_file.resolve().relative_to(program_dir.resolve())
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(modified_source, encoding="utf-8")

        # Incremental make — only the changed .c is recompiled, then relinked
        nproc = os.cpu_count() or 4
        flags = self.cfg.compiler.extra_cflags
        cmd = [
            "make", f"-j{nproc}",
            f"CFLAGS=-{opt} {flags}",
        ]
        t_start = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.cfg.compiler.timeout_seconds,
                cwd=str(workspace),
            )
        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False, program=program_name,
                function_name=func_name, operator=operator, seed=seed,
                opt=opt, cmd=" ".join(cmd),
                binary_path=None, workspace_path=str(workspace),
                compile_time=time.time() - t_start,
                stderr="make timeout",
            )

        elapsed = time.time() - t_start
        if proc.returncode != 0:
            return CompileResult(
                success=False, program=program_name,
                function_name=func_name, operator=operator, seed=seed,
                opt=opt, cmd=" ".join(cmd),
                binary_path=None, workspace_path=str(workspace),
                compile_time=elapsed,
                stderr=proc.stderr[:1000],
            )

        binary_path = self._find_function_binary(workspace, func_name) if func_name else None
        bsize = Path(binary_path).stat().st_size if binary_path else 0

        return CompileResult(
            success=True,
            program=program_name,
            function_name=func_name,
            operator=operator,
            seed=seed,
            opt=opt,
            cmd=" ".join(cmd),
            binary_path=binary_path,
            workspace_path=str(workspace),
            compile_time=elapsed,
            binary_size=bsize,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    # ------------------------------------------------------------------
    # Internal: binary location
    # ------------------------------------------------------------------

    @staticmethod
    def _find_function_binary(workspace: Path, func_name: str) -> str | None:
        """Search workspace for an ELF binary containing *func_name*."""
        ELFFile = _get_elftools()
        for f in workspace.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix in (".o", ".a", ".la", ".lo"):
                continue
            if not (f.stat().st_mode & 0o111):
                continue
            try:
                with f.open("rb") as fh:
                    if fh.read(4) != b"\x7fELF":
                        continue
                    fh.seek(0)
                    elf = ELFFile(fh)
                    symtab = elf.get_section_by_name(".symtab")
                    if not symtab:
                        symtab = elf.get_section_by_name(".dynsym")
                    if symtab:
                        for s in symtab.iter_symbols():
                            if s.name == func_name and s["st_size"] > 0:
                                return str(f)
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _touch_generated(workspace: Path):
        for f in workspace.rglob("*"):
            if f.is_file() and f.name in (
                "configure", "aclocal.m4", "Makefile.in",
                "config.h", "config.hin", "config.status",
            ):
                try:
                    f.touch()
                except OSError:
                    pass

    @staticmethod
    def _fix_permissions(workspace: Path):
        script_names = {"configure", "missing", "ylwrap", "depcomp",
                        "install-sh", "mkinstalldirs", "config.sub",
                        "config.guess", "compile", "ar-lib", "test-driver",
                        "py-compile", "help2man"}
        for f in workspace.rglob("*"):
            if f.is_file() and f.name in script_names:
                try:
                    f.chmod(0o755)
                except OSError:
                    pass

    @staticmethod
    def _fail(program: str, func_name: str, opt: str, reason: str) -> CompileResult:
        return CompileResult(
            success=False, program=program, function_name=func_name,
            operator=None, seed=None, opt=opt, cmd="",
            binary_path=None, workspace_path=None,
            compile_time=0, stderr=reason,
        )
