"""Semantic equivalence verification for SLOBF.

Generates a test harness that calls the target function with randomised inputs,
compiles and runs both original and obfuscated versions, and compares outputs
to confirm the obfuscation is semantics-preserving.
"""

from __future__ import annotations

import ctypes
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
        seed: int = 0,
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
        result_orig = self._compile_and_run(original_file, harness_code, func_info)
        result_obf = self._compile_and_run(obfuscated_file, harness_code, func_info)

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

        # Build the driver
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
        lines.append(f"    static unsigned char inputs[{self.num_cases}][{max(1, len(params)) * 8}];")

        # Seed random inputs
        lines.append(f"    srand((unsigned){rng.randint(1, 2**31-1)});")
        lines.append(f"    for (int _i = 0; _i < {self.num_cases}; _i++) {{")
        for j in range(len(params)):
            lines.append(f"        ((int *)(inputs[_i]))[{j}] = rand();")
        lines.append("    }")
        lines.append("")

        # Call function for each test case
        lines.append("    for (int _i = 0; _i < {self.num_cases}; _i++) {{")
        lines.append(f"        {ret_type} _ret = {func_info.name}(")
        args = []
        for j, _ in enumerate(params):
            args.append(f"((int *)(inputs[_i]))[{j}]")
        lines.append("            " + ", ".join(args) + ");")

        if ret_type == "void":
            lines.append('        printf("OK\\n");')
        elif ret_type in ("int", "unsigned", "unsigned int", "long", "long long", "size_t"):
            lines.append('        printf("%d\\n", (int)_ret);')
        elif ret_type in ("float", "double"):
            lines.append('        printf("%.6g\\n", (double)_ret);')
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
        """Extract parameter types from declaration strings."""
        result = []
        for p in param_types:
            p = p.strip()
            if p in ("void", ""):
                continue
            # Take the first word(s) before the last token (the parameter name)
            tokens = p.split()
            if len(tokens) >= 2:
                type_str = " ".join(tokens[:-1])
            else:
                type_str = tokens[0]
            normalised = self._normalise_type(type_str)
            if normalised is None:
                return None
            result.append(normalised)
        return result

    # ------------------------------------------------------------------
    # Compile & run
    # ------------------------------------------------------------------

    def _compile_and_run(
        self, source_file: Path, harness_code: str, func_info: FunctionInfo,
    ) -> dict[str, Any]:
        """Create a temp directory, compile harness + source, run, return output."""
        tmpdir = Path(tempfile.mkdtemp(prefix="slobf_sem_"))

        try:
            harness_path = tmpdir / "harness.c"
            harness_path.write_text(harness_code, encoding="utf-8")

            # Copy the source file to the temp dir
            source_copy = tmpdir / source_file.name
            source_copy.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")

            binary = tmpdir / "test.elf"
            cmd = [self.cc, "-O0", "-o", str(binary), str(harness_path), str(source_copy)]

            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout,
            )
            if proc.returncode != 0:
                return {"error": f"Compile failed: {proc.stderr[:500]}"}

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
