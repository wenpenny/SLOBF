"""Integration tests: apply each obfuscator, compile, run, and verify output.

Uses test_functions.c as input. Each eligible function is obfuscated,
the modified source is compiled, and the resulting binary is run.
Output is compared to the baseline to confirm semantics are preserved.
"""

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from slobf.config import load_config, CompilerConfig
from slobf.obfuscators.manager import ObfuscationManager
from slobf.parser.c_parser import CParser, FunctionInfo

TEST_C_FILE = Path(__file__).parent / "test_functions.c"
GCC = "gcc"


def compile_and_run(source_path: Path, timeout: int = 30) -> tuple[bool, str, str]:
    """Compile a C file and run it. Returns (success, stdout, stderr)."""
    binary = source_path.with_suffix(".exe")
    try:
        proc = subprocess.run(
            [GCC, "-O0", "-o", str(binary), str(source_path)],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "", "Compile timeout"

    if proc.returncode != 0:
        return False, "", proc.stderr[:500]

    try:
        proc = subprocess.run(
            [str(binary)], capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "", "Runtime timeout"

    # Clean up binary
    if binary.exists():
        binary.unlink()

    return proc.returncode == 0, proc.stdout, proc.stderr


def apply_operator_to_function(source_path: Path, func_name: str,
                                operator_name: str, seed: int = 42) -> str | None:
    """Apply an obfuscation operator to a single function. Returns modified source or None."""
    cfg = load_config()
    cfg.compiler = CompilerConfig(cc=GCC)

    parser = CParser()
    mgr = ObfuscationManager(cfg)

    # Get the real FunctionInfo from the parser (not an empty shell)
    all_funcs = parser.parse_file(source_path)
    func_info = next((f for f in all_funcs if f.name == func_name), None)
    if func_info is None:
        return None

    result = mgr.obfuscate_function_in_file(
        source_path, func_info, operator_name, seed=seed, intensity=1.0,
    )
    if not result or not result.success:
        return None
    return result.changed_source


def write_test_source(original: Path, modified_source: str) -> Path:
    """Write modified source to a temp file and return its path."""
    tmpdir = Path(tempfile.mkdtemp(prefix="slobf_test_"))
    dest = tmpdir / original.name
    dest.write_text(modified_source, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Test cases: (function_name, operator, should_succeed, should_preserve_semantics)
# ---------------------------------------------------------------------------

OPERATOR_TESTS = [
    # OPI — wraps statements in opaque predicates
    ("opi_add", "OPI", True, True),

    # CFF — flattens control flow
    ("cff_classify", "CFF", True, True),
    ("cff_sum_range", "CFF", True, True),
    # CFF should REJECT functions with break or continue
    ("cff_find_positive", "CFF", False, False),
    ("cff_count_even", "CFF", False, False),

    # ER — rewrites expressions
    ("er_arithmetic", "ER", True, True),
    ("er_logical", "ER", True, True),
    ("er_pre_inc", "ER", True, True),

    # DE — encodes constants and strings
    ("de_constants", "DE", True, True),
    ("de_message", "DE", True, True),

    # JCI — inserts junk code
    ("jci_process", "JCI", True, True),

    # FS — splits function
    ("fs_long_compute", "FS", True, True),
    # FS: function with float type (tests non-int param handling)
    ("fs_float_op", "FS", True, True),
    # FS should REJECT functions with multiple returns
    ("fs_multi_return", "FS", False, False),

    # Compound test with all operators
    ("compound_basic", "OPI", True, True),
    ("compound_basic", "ER", True, True),
    ("compound_basic", "DE", True, True),
    ("compound_basic", "JCI", True, True),
]


class TestObfuscatorSemantics:
    """For each (function, operator) pair: obfuscate, compile, run, compare."""

    @pytest.mark.parametrize("func_name,operator,should_succeed,should_preserve", OPERATOR_TESTS)
    def test_operator(self, func_name, operator, should_succeed, should_preserve):
        if not TEST_C_FILE.exists():
            pytest.skip(f"{TEST_C_FILE} not found")

        # Get baseline output
        ok, baseline_out, baseline_err = compile_and_run(TEST_C_FILE)
        assert ok, f"Baseline compile/run failed: {baseline_err}"

        # Apply operator
        modified = apply_operator_to_function(TEST_C_FILE, func_name, operator)
        if not should_succeed:
            assert modified is None, (
                f"{operator} on {func_name} should have been rejected "
                f"(e.g., break/continue in CFF, multi-return in FS)"
            )
            return

        assert modified is not None, (
            f"{operator} failed on {func_name} — returned None"
        )

        # Source must differ from original
        original_source = TEST_C_FILE.read_text(encoding="utf-8")
        assert modified != original_source, (
            f"{operator} on {func_name}: source unchanged"
        )

        # Compile modified source
        tmp_path = write_test_source(TEST_C_FILE, modified)
        try:
            ok, out, err = compile_and_run(tmp_path)
            if not should_preserve:
                return  # expected to fail

            assert ok, (
                f"{operator} on {func_name}: compile/run failed\n"
                f"stderr: {err[:500]}"
            )
            assert out.strip() == baseline_out.strip(), (
                f"{operator} on {func_name}: output diverges from baseline\n"
                f"Expected: {baseline_out.strip()[:200]}\n"
                f"Got:      {out.strip()[:200]}"
            )
        finally:
            # Cleanup temp files
            shutil.rmtree(tmp_path.parent, ignore_errors=True)


class TestObfuscatorSourceChange:
    """Verify each operator actually changes the source (not a no-op)."""

    SIMPLE_TESTS = [
        ("opi_add", "OPI"),
        ("cff_classify", "CFF"),
        ("er_arithmetic", "ER"),
        ("de_constants", "DE"),
        ("jci_process", "JCI"),
        ("fs_long_compute", "FS"),
    ]

    @pytest.mark.parametrize("func_name,operator", SIMPLE_TESTS)
    def test_source_differs(self, func_name, operator):
        modified = apply_operator_to_function(TEST_C_FILE, func_name, operator)
        assert modified is not None, f"{operator} on {func_name} returned None"
        original = TEST_C_FILE.read_text(encoding="utf-8")
        assert modified != original, f"{operator} on {func_name} did not modify source"

        # Source hash must differ
        h1 = hashlib.sha256(original.encode()).hexdigest()
        h2 = hashlib.sha256(modified.encode()).hexdigest()
        assert h1 != h2, f"{operator} on {func_name}: source hash unchanged"


class TestOperatorStacking:
    """Verify operators can be applied in sequence."""

    def test_opi_then_er(self):
        """OPI then ER: both should apply and preserve semantics."""
        # Step 1: OPI
        after_opi = apply_operator_to_function(TEST_C_FILE, "opi_add", "OPI")
        assert after_opi is not None, "OPI failed"
        tmp1 = write_test_source(TEST_C_FILE, after_opi)

        try:
            # Step 2: ER on OPI-modified source
            after_er = apply_operator_to_function(tmp1, "opi_add", "ER")
            assert after_er is not None, "ER after OPI failed"
            assert after_er != after_opi, "ER after OPI: source unchanged"

            # Compile and run
            tmp2 = write_test_source(TEST_C_FILE, after_er)
            try:
                ok, out, err = compile_and_run(tmp2)
                # Get baseline
                _, baseline_out, _ = compile_and_run(TEST_C_FILE)
                assert ok, f"Stack OPI+ER compile failed: {err[:300]}"
                assert out.strip() == baseline_out.strip(), "Stack OPI+ER output mismatch"
            finally:
                shutil.rmtree(tmp2.parent, ignore_errors=True)
        finally:
            shutil.rmtree(tmp1.parent, ignore_errors=True)

    def test_jci_then_de(self):
        """JCI then DE: both should apply and preserve semantics."""
        after_jci = apply_operator_to_function(TEST_C_FILE, "de_constants", "JCI")
        assert after_jci is not None, "JCI failed"
        tmp1 = write_test_source(TEST_C_FILE, after_jci)

        try:
            after_de = apply_operator_to_function(tmp1, "de_constants", "DE")
            assert after_de is not None, "DE after JCI failed"
            assert after_de != after_jci, "DE after JCI: source unchanged"

            tmp2 = write_test_source(TEST_C_FILE, after_de)
            try:
                ok, out, err = compile_and_run(tmp2)
                _, baseline_out, _ = compile_and_run(TEST_C_FILE)
                assert ok, f"Stack JCI+DE compile failed: {err[:300]}"
                assert out.strip() == baseline_out.strip(), "Stack JCI+DE output mismatch"
            finally:
                shutil.rmtree(tmp2.parent, ignore_errors=True)
        finally:
            shutil.rmtree(tmp1.parent, ignore_errors=True)
