"""Control Flow Flattening (CFF) obfuscator."""

import random
from typing import Any
from tree_sitter import Node
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult


class CFFObfuscator:
    name = "CFF"

    def is_eligible(self, node: Node, func_meta: dict[str, Any]) -> tuple[bool, str]:
        if func_meta.get("num_statements", 0) < 5:
            return False, "Too few statements"
        if func_meta.get("has_goto", False):
            return False, "Contains goto"
        return True, ""

    def transform(self, source_text: str, node: Node, func_meta: dict[str, Any], 
                  seed: int, intensity: float) -> ObfuscationResult:
        random.seed(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_meta.get("name", "unknown"), seed=seed, intensity=intensity
        )

        # Simplified CFF: Wrap the entire body in a switch-case dispatcher
        # This is a complex transformation; for the skeleton, we'll implement a basic version
        # that targets simple sequential blocks.
        
        lines = source_text.splitlines()
        body_start = -1
        body_end = -1
        for i, line in enumerate(lines):
            if '{' in line and body_start == -1:
                body_start = i
            if '}' in line:
                body_end = i
        
        if body_start == -1 or body_end == -1 or body_end <= body_start + 1:
            res.reason_if_failed = "Could not identify function body"
            return res

        original_body = lines[body_start+1:body_end]
        
        state_var = f"slobf_state_{random.randint(0, 1000)}"
        new_body = [
            f"    int {state_var} = 0;",
            f"    while ({state_var} != -1) {{",
            f"        switch ({state_var}) {{",
            "            case 0:",
        ]
        
        # In a real implementation, we would split original_body into basic blocks.
        # Here we just put everything in one case and exit.
        for line in original_body:
            new_body.append(f"            {line}")
        
        new_body.append(f"                {state_var} = -1;")
        new_body.append("                break;")
        new_body.append("            default:")
        new_body.append(f"                {state_var} = -1;")
        new_body.append("                break;")
        new_body.append("        }")
        new_body.append("    }")

        final_lines = lines[:body_start+1] + new_body + lines[body_end:]
        res.changed_source = "\n".join(final_lines)
        res.compute_diff(source_text)
        res.success = True
        return res
