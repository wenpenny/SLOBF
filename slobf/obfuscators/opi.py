"""Opaque Predicate Insertion (OPI) — AST-based.

Implements the classic opaque predicate technique (Collberg et al., "Breaking
Abstractions and Unstructuring Data Structures"):
- Inserts if-then-else branches guarded by predicates that are always-true
  (or always-false) but computationally hard for static analysis to prove.
- The 'then' branch contains the original code (for always-true predicates).
- The 'else' branch contains dead bogus code that never executes.
- Multiple mathematical identities for predicate diversity.
"""

from __future__ import annotations

import random
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.parser.c_parser import FunctionInfo
from tree_sitter import Node


class OPIObfuscator(BaseObfuscator):
    name = "OPI"

    # Always-true predicates (mathematical identities)
    _ALWAYS_TRUE = [
        "(({v} * {v}) >= 0)",
        "(({v} * {v} + 1) % 2 == 1)",
        "(({v} | 0xFFFFFFFF) == 0xFFFFFFFF)",
        "(({v} ^ {v}) == 0)",
        "(((unsigned int){v} + 1) > (unsigned int){v})",
        "(({v} & 0x1) == (({v} % 2) != 0))",
        "(({v} > 0) || ({v} <= 0))",
        "(({v} << 3) + ({v} << 1) == {v} * 10)",
    ]

    # Always-false predicates
    _ALWAYS_FALSE = [
        "(({v} * {v}) < 0)",
        "(({v} | 0xFFFFFFFF) != 0xFFFFFFFF)",
        "(({v} ^ {v}) != 0)",
        "(((unsigned int){v} + 1) < (unsigned int){v})",
        "(({v} & 0x1) != (({v} % 2) != 0))",
    ]

    def is_eligible(self, func_info: FunctionInfo) -> tuple[bool, str]:
        ok, reason = super().is_eligible(func_info)
        if not ok:
            return ok, reason
        if func_info.num_statements < 2:
            return False, "Too few statements for OPI (< 2)"
        return True, ""

    def transform(self, source: bytes, func_node: Node, func_info: FunctionInfo,
                  seed: int, intensity: float) -> ObfuscationResult:
        rng = random.Random(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_info.name, seed=seed, intensity=intensity
        )

        # Locate function body
        body = None
        for child in func_node.children:
            if child.type == "compound_statement":
                body = child
                break
        if not body:
            res.reason_if_failed = "No function body found"
            return res

        stmts = [c for c in body.children if c.type not in ("{", "}")]
        if not stmts:
            res.reason_if_failed = "No statements to wrap"
            return res

        # Skip declarations: wrapping them in if-blocks breaks variable scoping
        wrappable = [s for s in stmts if s.type != "declaration"]
        if not wrappable:
            res.reason_if_failed = "No wrappable statements (only declarations)"
            return res

        num_inserts = max(1, min(len(wrappable) // 2, int(intensity * 5)))
        chosen = rng.sample(wrappable, num_inserts)

        var_base = f"slobf_opi_{rng.randint(10000, 99999)}"
        new_source = source

        # Process in reverse byte order
        for i, stmt in enumerate(sorted(chosen, key=lambda n: n.start_byte, reverse=True)):
            stmt_text = new_source[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="ignore")
            inner = stmt_text.rstrip()

            var_name = f"{var_base}_{i}"
            indent = " " * stmt.start_point[1]

            # Mix of always-true (wrap original) and always-false (wrap bogus)
            use_true = rng.choice([True, False])

            if use_true:
                pred = rng.choice(self._ALWAYS_TRUE).format(v=var_name)
                bogus = self._gen_bogus_block(var_base, i, indent, rng)
                wrapped = (
                    f"{indent}volatile int {var_name} = {rng.randint(1, 0x7FFF)};\n"
                    f"{indent}if {pred} {{\n"
                    f"{indent}    {inner}\n"
                    f"{indent}}} else {{\n"
                    f"{bogus}"
                    f"{indent}}}"
                )
            else:
                pred = rng.choice(self._ALWAYS_FALSE).format(v=var_name)
                bogus = self._gen_bogus_block(var_base, i, indent, rng)
                wrapped = (
                    f"{indent}volatile int {var_name} = {rng.randint(1, 0x7FFF)};\n"
                    f"{indent}if {pred} {{\n"
                    f"{bogus}"
                    f"{indent}}} else {{\n"
                    f"{indent}    {inner}\n"
                    f"{indent}}}"
                )

            new_source = (new_source[:stmt.start_byte] +
                          wrapped.encode() +
                          new_source[stmt.end_byte:])

        res.changed_source = new_source.decode("utf-8", errors="ignore")
        res.compute_diff(source.decode("utf-8", errors="ignore"))
        res.success = True
        res.metadata["predicates_inserted"] = num_inserts
        return res

    @staticmethod
    def _gen_bogus_block(var_base: str, idx: int, indent: str, rng: random.Random) -> str:
        """Generate dead code for the never-executed branch."""
        jv = f"{var_base}_j{idx}"
        templates = [
            f"{indent}    volatile int {jv} = {rng.randint(1, 0xFF)};\n"
            f"{indent}    {jv} = ({jv} << 7) | ({jv} >> 25);\n"
            f"{indent}    if ({jv} == 0) {{ {jv} = 1; }}\n",

            f"{indent}    unsigned int {jv} = (unsigned int)-1;\n"
            f"{indent}    {jv} ^= {rng.randint(0x1000, 0xFFFF)};\n"
            f"{indent}    {jv} += ({jv} % 256) * {rng.randint(1, 100)};\n",

            f"{indent}    int {jv} = {rng.randint(1, 0xFFFF)};\n"
            f"{indent}    while ({jv} > 0) {{ {jv} >>= 1; }}\n"
            f"{indent}    (void){jv};\n",
        ]
        return rng.choice(templates)
