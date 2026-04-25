"""Expression Rewriting (ER) obfuscator."""

import random
import re
from typing import Any
from tree_sitter import Node
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult


class ERObfuscator:
    name = "ER"

    def is_eligible(self, node: Node, func_meta: dict[str, Any]) -> tuple[bool, str]:
        # We need at least some arithmetic or constants
        return True, ""

    def transform(self, source_text: str, node: Node, func_meta: dict[str, Any], 
                  seed: int, intensity: float) -> ObfuscationResult:
        random.seed(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_meta.get("name", "unknown"), seed=seed, intensity=intensity
        )

        # Simple regex-based rewriting for integers and common operators
        # In a real version, we'd use the AST to be safer.
        
        new_source = source_text
        
        # a + b -> a - (-b)
        def add_rewrite(match):
            a, b = match.groups()
            return f"{a} - (-{b})"
        
        # x * 2 -> (x << 1) or (x + x)
        def mul2_rewrite(match):
            x = match.group(1)
            return f"({x} + {x})"

        # Apply a few rewrites
        new_source = re.sub(r"(\w+)\s*\+\s*(\w+)", add_rewrite, new_source, count=2)
        new_source = re.sub(r"(\w+)\s*\*\s*2", mul2_rewrite, new_source, count=1)
        
        if new_source != source_text:
            res.changed_source = new_source
            res.compute_diff(source_text)
            res.success = True
        else:
            res.reason_if_failed = "No expressions matched for rewriting"

        return res
