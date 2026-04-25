"""Junk Code Insertion (JCI) obfuscator."""

import random
from typing import Any
from tree_sitter import Node
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult


class JCIObfuscator:
    name = "JCI"

    def is_eligible(self, node: Node, func_meta: dict[str, Any]) -> tuple[bool, str]:
        if func_meta.get("num_statements", 0) < 3:
            return False, "Too few statements"
        return True, ""

    def transform(self, source_text: str, node: Node, func_meta: dict[str, Any], 
                  seed: int, intensity: float) -> ObfuscationResult:
        random.seed(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_meta.get("name", "unknown"), seed=seed, intensity=intensity
        )

        lines = source_text.splitlines()
        new_lines = []
        inserted = False
        
        junk_var = f"slobf_j_{random.randint(0, 1000)}"
        
        for line in lines:
            new_lines.append(line)
            if '{' in line and not inserted:
                indent = "    "
                new_lines.append(f"{indent}volatile int {junk_var} = {random.randint(0, 100)};")
                for _ in range(int(intensity * 3)):
                    op = random.choice(["+=", "-=", "^="])
                    val = random.randint(1, 1000)
                    new_lines.append(f"{indent}{junk_var} {op} {val};")
                inserted = True

        if inserted:
            res.changed_source = "\n".join(new_lines)
            res.compute_diff(source_text)
            res.success = True
        else:
            res.reason_if_failed = "Could not find insertion point"

        return res
