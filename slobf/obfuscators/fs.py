"""Function Splitting (FS) obfuscator."""

import random
from typing import Any
from tree_sitter import Node
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult


class FSObfuscator:
    name = "FS"

    def is_eligible(self, node: Node, func_meta: dict[str, Any]) -> tuple[bool, str]:
        if func_meta.get("num_statements", 0) < 8:
            return False, "Too few statements"
        return True, ""

    def transform(self, source_text: str, node: Node, func_meta: dict[str, Any], 
                  seed: int, intensity: float) -> ObfuscationResult:
        random.seed(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_meta.get("name", "unknown"), seed=seed, intensity=intensity
        )

        # Simplified FS: Extract a part of the body into a helper function
        # This is a very complex transformation to do correctly at source level.
        # For the skeleton, we'll demonstrate the concept by splitting the body.
        
        lines = source_text.splitlines()
        body_start = -1
        body_end = -1
        for i, line in enumerate(lines):
            if '{' in line and body_start == -1:
                body_start = i
            if '}' in line:
                body_end = i
        
        if body_start == -1 or body_end == -1 or (body_end - body_start) < 5:
            res.reason_if_failed = "Body too small to split"
            return res

        # Split point
        mid = (body_start + body_end) // 2
        helper_body = lines[body_start+1:mid]
        main_body = lines[mid:body_end]
        
        helper_name = f"slobf_helper_{random.randint(0, 1000)}"
        
        # Note: This skeleton doesn't handle parameters/return correctly.
        # It assumes the helper can be void and takes no params.
        helper_func = [
            f"static void {helper_name}() {{",
        ] + helper_body + ["}"]
        
        new_main_body = [
            f"    {helper_name}();"
        ] + main_body
        
        final_source = "\n".join(helper_func) + "\n\n" + "\n".join(lines[:body_start+1] + new_main_body + lines[body_end:])
        
        res.changed_source = final_source
        res.compute_diff(source_text)
        res.success = True
        return res
