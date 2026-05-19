"""Semantic equivalence verification for SLOBF.

Generates a test harness that calls the target function with randomised inputs,
compiles and runs both original and obfuscated versions, and compares outputs
to confirm the obfuscation is semantics-preserving.
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from slobf.parser.c_parser import FunctionInfo

logger = logging.getLogger(__name__)


class SemanticVerifier:
    """Checks that an obfuscated function behaves identically to the original."""

    def __init__(self, cc: str = "gcc", num_cases: int = 50, timeout: int = 10):
        self.cc = cc
        self.num_cases = num_cases
        self.timeout = timeout

    def verify(
        self,
        original_file: Path,
        obfuscated_file: Path,
        func_info: FunctionInfo,
        seed: int = 0, build_dir: str | None = None,
    ) -> dict[str, Any]:
        """Build and run test harnesses for original and obfuscated, compare.

        Returns a dict with keys: passed, total_cases, mismatches, error, harness_code.
        """
        rng = random.Random(seed)

        # Generate the test harness
        harness_code = self._build_harness(func_info, rng)
        if harness_code is None:
            return {"passed": False, "total_cases": 0, "error": "Cannot build harness for signature"}

        # Compile and run
        result_orig = self._compile_and_run(original_file, harness_code, func_info, build_dir)
        result_obf = self._compile_and_run(obfuscated_file, harness_code, func_info, build_dir)

        if result_orig.get("error"):
            return {"passed": False, "total_cases": 0, "error": f"Original: {result_orig['error']}"}
        if result_obf.get("error"):
            return {"passed": False, "total_cases": 0, "error": f"Obfuscated: {result_obf['error']}"}

        orig_out = result_orig["output"]
        obf_out = result_obf["output"]
        mismatches = []
        lines_orig = orig_out.strip().splitlines()
        lines_obf = obf_out.strip().splitlines()

        total = min(len(lines_orig), len(lines_obf))
        for i in range(total):
            if lines_orig[i].strip() != lines_obf[i].strip():
                mismatches.append({"case": i, "original": lines_orig[i], "obfuscated": lines_obf[i]})

        passed = len(mismatches) == 0 and total > 0
        return {
            "passed": passed,
            "total_cases": total,
            "mismatches": mismatches,
            "output_original": orig_out[:2000],
            "output_obfuscated": obf_out[:2000],
        }

    # ------------------------------------------------------------------
    # Harness generation
    # ------------------------------------------------------------------

    def _build_harness(self, func_info: FunctionInfo, rng: random.Random) -> str | None:
        """Generate a standalone test harness that calls the target function.

        Returns C source code as a string, or None if the signature cannot be handled.
        """
        ret_type = self._normalise_type(func_info.return_type)
        if ret_type is None:
            return None

        params = self._parse_params(func_info.param_types)
        if params is None:
            return None

        lines = []
        lines.append("/* Auto-generated semantic equivalence harness */")
        lines.append('#include <stdio.h>')
        lines.append('#include <stdlib.h>')
        lines.append('#include <string.h>')
        lines.append('#include <stdint.h>')
        lines.append("")

        # Declare the target function
        param_decls = ", ".join(f"{t} p{i}" for i, t in enumerate(params))
        lines.append(f"{ret_type} {func_info.name}({param_decls});")
        lines.append("")

        lines.append("int main(void) {")
        lines.append("    static char _ptr_buf[256];")
        lines.append(f"    srand((unsigned){rng.randint(1, 2**31-1)});")
        lines.append("")

        n_params = len(params)

        lines.append(f"    for (int _i = 0; _i < {self.num_cases}; _i++) {{")

        # Generate type-appropriate random input for each parameter
        for j, ptype in enumerate(params):
            if ptype == "void*" or "*" in ptype:
                # Give a valid non-null buffer slice so dereference won't segfault
                lines.append(f"        void *p{j} = &_ptr_buf[_i % 192];")
            elif ptype in ("float",):
                lines.append(f"        float p{j} = (float)rand() / (float)RAND_MAX * 100.0f;")
            elif ptype in ("double",):
                lines.append(f"        double p{j} = (double)rand() / (double)RAND_MAX * 100.0;")
            elif ptype in ("char", "unsigned char", "int8_t", "uint8_t"):
                lines.append(f"        {ptype} p{j} = ({ptype})(rand() & 0xFF);")
            elif ptype in ("short", "unsigned short", "int16_t", "uint16_t"):
                lines.append(f"        {ptype} p{j} = ({ptype})(rand() & 0xFFFF);")
            elif ptype in ("uint64_t", "int64_t", "long long", "unsigned long long"):
                lines.append(
                    f"        {ptype} p{j} = ({ptype})"
                    f"(((uint64_t)rand() << 32) | (uint32_t)rand());"
                )
            else:
                # int, unsigned, long, unsigned long, size_t, etc.
                lines.append(f"        {ptype} p{j} = ({ptype})rand();")

        # Call function
        args = ", ".join(f"p{j}" for j in range(n_params))
        if ret_type == "void":
            lines.append(f"        {func_info.name}({args});")
            lines.append('        printf("OK\\n");')
        else:
            lines.append(f"        {ret_type} _ret = {func_info.name}({args});")
            if ret_type in ("float", "double"):
                lines.append('        printf("%.10g\\n", (double)_ret);')
            elif ret_type in ("uint64_t", "int64_t", "long long",
                             "unsigned long long"):
                lines.append('        printf("%lld\\n", (long long)_ret);')
            elif ret_type in ("int", "unsigned", "unsigned int", "long",
                             "unsigned long", "size_t", "short", "char",
                             "unsigned char", "unsigned short",
                             "int8_t", "uint8_t", "int16_t", "uint16_t",
                             "int32_t", "uint32_t"):
                lines.append('        printf("%d\\n", (int)_ret);')
            else:
                lines.append('        printf("%p\\n", (void*)_ret);')

        lines.append("    }")
        lines.append("    return 0;")
        lines.append("}")

        return "\n".join(lines)

    def _normalise_type(self, t: str) -> str | None:
        """Return a simplified type name, or None if unsupported."""
        if not t:
            return "int"  # implicit int
        t = t.strip()
        # Remove storage class / qualifiers
        for kw in ["static", "extern", "const", "volatile", "register"]:
            t = t.replace(kw, "").strip()
        if t in ("void", "int", "char", "short", "long", "float", "double",
                 "unsigned", "unsigned int", "unsigned char", "unsigned short",
                 "unsigned long", "long long", "size_t", "uint8_t", "uint16_t",
                 "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t", "int64_t"):
            return t
        if "*" in t:
            return "void*"
        return "int"  # fallback

    def _parse_params(self, param_types: list[str]) -> list[str] | None:
        """Extract parameter types from declaration strings.

        Handles: "int x", "const char *s", "int *p", "char **argv"
        """
        result = []
        for p in param_types:
            p = p.strip()
            if p in ("void", ""):
                continue
            tokens = p.split()
            if not tokens:
                continue
            # The last token may be "*name", "**name", or just "name".
            # Separate pointer-stars from the identifier.
            last = tokens[-1]
            stars = ""
            if last.startswith("*"):
                i = 0
                while i < len(last) and last[i] == "*":
                    stars += "*"
                    i += 1
                identifier = last[i:]
                if identifier:
                    # "*name" case — stars go to the type part
                    if len(tokens) >= 2:
                        type_str = " ".join(tokens[:-1]) + " " + stars
                    else:
                        type_str = stars
                else:
                    # "***" only (unlikely) — whole is type
                    type_str = " ".join(tokens)
            elif len(tokens) >= 2:
                # "int x" case — last token is the identifier
                type_str = " ".join(tokens[:-1])
            else:
                # Single token, not a pointer-star — type only (e.g., "int")
                type_str = tokens[0]

            normalised = self._normalise_type(type_str.strip())
            if normalised is None:
                return None
            result.append(normalised)
        return result

    # ------------------------------------------------------------------
    # Compile & run
    # ------------------------------------------------------------------

    def _compile_and_run(
        self, source_file: Path, harness_code: str, func_info: FunctionInfo,
        build_dir: str | None = None,
    ) -> dict[str, Any]:
        """Create a temp directory, compile harness + source, run, return output.

        The provided *source_file* is always compiled to a .o and linked first,
        so the target function comes from the correct (original or obfuscated)
        source.  .a archives from the build workspace are linked afterwards
        purely for dependency resolution.
        """
        tmpdir = Path(tempfile.mkdtemp(prefix="slobf_sem_"))

        try:
            harness_path = tmpdir / "harness.c"
            harness_path.write_text(harness_code, encoding="utf-8")

            # Copy the source file to the temp dir
            source_copy = tmpdir / source_file.name
            source_copy.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")

            binary = tmpdir / "test.elf"
            inc_flags = []
            inc_flags.append(f"-I{source_file.resolve().parent}")
            # Find config.h in parent directories and force-include it
            for p in source_file.resolve().parents:
                config_h = p / "config.h"
                if config_h.exists():
                    inc_flags.append(f"-I{p.resolve()}")
                    inc_flags.append("-include")
                    inc_flags.append(str(config_h.resolve()))
                    break

            # 1. Compile the source file (original OR obfuscated) to a .o first.
            #    This ensures the target function comes from the correct source.
            #    -Dmain=... renames any source-level main() so it never clashes
            #    with the harness's own main().  Only the identifier 'main' is
            #    affected; string literals and struct members are untouched.
            source_o = tmpdir / (source_file.stem + ".o")
            proc = subprocess.run(
                [self.cc, "-O0", "-w", "-Dmain=slobf_renamed_main"]
                + inc_flags
                + ["-c", str(source_copy), "-o", str(source_o)],
                capture_output=True, text=True, timeout=self.timeout,
            )
            if proc.returncode != 0:
                return {"error": f"Compile source failed: {proc.stderr[:500]}"}

            # 2. Collect .a archives for dependency resolution only.
            _skip_dirs = {"tests", "gnulib-tests", "test", "testing"}
            lib_files = []
            o_dirs = []
            if build_dir:
                bd = Path(build_dir)
                if bd.exists():
                    o_dirs.append(bd)
            if not o_dirs:
                prog_root = source_file.resolve().parent
                for p in source_file.resolve().parents:
                    if (p / "Makefile").exists() or (p / "makefile").exists():
                        prog_root = p
                        break
                o_dirs.append(prog_root)
            for d in o_dirs:
                for a in d.rglob("*.a"):
                    if any(sd in a.parent.parts for sd in _skip_dirs):
                        continue
                    lib_files.append(str(a.resolve()))
                    if len(lib_files) >= 50:
                        break
                if len(lib_files) >= 50:
                    break

            # 3. Link: harness.o (main) + source.o (target function) + .a (deps).
            cmd = (
                [self.cc, "-O0", "-w"] + inc_flags
                + ["-o", str(binary), str(harness_path), str(source_o)]
                + lib_files
            )

            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout,
            )
            if proc.returncode != 0:
                return {"error": f"Link failed: {proc.stderr[:500]}"}

            proc = subprocess.run(
                [str(binary)], capture_output=True, text=True, timeout=self.timeout,
            )
            return {"output": proc.stdout, "stderr": proc.stderr}
        except subprocess.TimeoutExpired:
            return {"error": "timeout"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            # Clean up temp directory
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
