"""Junk Code Insertion (JCI) — AST-based."""

import random
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.parser.c_parser import FunctionInfo
from tree_sitter import Node


class JCIObfuscator(BaseObfuscator):
    name = "JCI"

    def is_eligible(self, func_info: FunctionInfo) -> tuple[bool, str]:
        ok, reason = super().is_eligible(func_info)
        if not ok:
            return ok, reason
        if func_info.num_statements < 2:
            return False, "Too few statements for junk insertion"
        return True, ""

    def transform(self, source: bytes, func_node: Node, func_info: FunctionInfo,
                  seed: int, intensity: float) -> ObfuscationResult:
        rng = random.Random(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_info.name, seed=seed, intensity=intensity
        )

        body = None
        for child in func_node.children:
            if child.type == "compound_statement":
                body = child
                break
        if not body:
            res.reason_if_failed = "No function body"
            return res

        stmts = [c for c in body.children if c.type not in ("{", "}")]
        if not stmts:
            res.reason_if_failed = "No statements in body"
            return res

        num_inserts = max(1, int(intensity * min(len(stmts), 5)))
        insert_after = rng.sample(range(len(stmts)), min(num_inserts, len(stmts)))

        new_source = source
        # Process in reverse order
        for idx in sorted(insert_after, reverse=True):
            stmt = stmts[idx]
            junk = self._generate_junk(stmt, rng)
            # Insert junk AFTER this statement (at its end_byte)
            insert_pos = stmt.end_byte
            new_source = (new_source[:insert_pos] +
                          b"\n" + junk.encode() +
                          new_source[insert_pos:])

        res.changed_source = new_source.decode("utf-8", errors="ignore")
        res.compute_diff(source.decode("utf-8", errors="ignore"))
        res.success = True
        res.metadata["junk_blocks_inserted"] = num_inserts
        return res

    def _generate_junk(self, anchor_stmt: Node, rng: random.Random) -> str:
        indent = " " * anchor_stmt.start_point[1]
        var = f"slobf_j_{rng.randint(1000, 9999)}"

        templates = [
            f"{indent}volatile int {var} = {rng.randint(1, 0xFFF)};\n" +
            f"{indent}{var} ^= {rng.randint(1, 0xFFF)};\n" +
            f"{indent}{var} += {rng.randint(1, 100)};\n" +
            f"{indent}(void){var};",

            f"{indent}unsigned int {var} = (unsigned int){rng.randint(1, 0xFFFF)};\n" +
            f"{indent}{var} = ({var} << 3) | ({var} >> 29);\n" +
            f"{indent}if (({var} & 0x1) == ({var} % 2)) {{ (void)0; }}",

            f"{indent}int {var} = {rng.randint(1, 100)};\n" +
            f"{indent}while ({var} > 0) {{ {var}--; }}\n" +
            f"{indent}(void){var};",

            f"{indent}volatile float {var} = (float){rng.randint(1, 1000)};\n" +
            f"{indent}{var} = {var} * 2.0f - {var};\n" +
            f"{indent}if ({var} == 0.0f) {{ /* dead */ }}",
        ]
        return rng.choice(templates)
