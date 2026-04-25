"""Opaque Predicate Insertion (OPI) obfuscator."""

import random
from typing import Any
from tree_sitter import Node
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult


class OPIObfuscator:
    name = "OPI"

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

        # Find a suitable insertion point in the compound statement
        body = None
        for child in node.children:
            if child.type == "compound_statement":
                body = child
                break
        
        if not body or len(body.children) < 3: # { ... }
            res.reason_if_failed = "No suitable body found"
            return res

        # Simple strategy: insert at the beginning of the body
        # or wrap a random statement.
        
        # Opaque predicate templates
        templates = [
            "if (((slobf_v * slobf_v) >= 0) || (slobf_v != slobf_v))",
            "if ((slobf_v % 2 == 0) || (slobf_v % 2 != 0))",
        ]
        
        predicate = random.choice(templates)
        var_name = f"slobf_v_{random.randint(0, 1000)}"
        
        # Construct the obfuscated source
        # We'll just wrap the first statement for simplicity in this version
        lines = source_text.splitlines()
        
        # Find the first '{' and insert after it
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if '{' in line and not inserted:
                indent = "    " # Simple indent
                new_lines.append(f"{indent}volatile int {var_name} = {random.randint(1, 10000)};")
                new_lines.append(f"{indent}{predicate} {{")
                new_lines.append(f"{indent}    // original logic follows")
                inserted = True
        
        # Close the if block at the end
        if inserted:
            # Find the last '}'
            for i in range(len(new_lines) - 1, -1, -1):
                if '}' in new_lines[i]:
                    new_lines.insert(i, "    }")
                    break
            
            res.changed_source = "\n".join(new_lines)
            res.compute_diff(source_text)
            res.success = True
            res.metadata["predicate"] = predicate
            res.metadata["variable"] = var_name

        return res
