"""Data Encoding (DE) obfuscator."""

import random
import re
from typing import Any
from tree_sitter import Node
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult


class DEObfuscator:
    name = "DE"

    def is_eligible(self, node: Node, func_meta: dict[str, Any]) -> tuple[bool, str]:
        # Need some constants
        return True, ""

    def transform(self, source_text: str, node: Node, func_meta: dict[str, Any], 
                  seed: int, intensity: float) -> ObfuscationResult:
        random.seed(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_meta.get("name", "unknown"), seed=seed, intensity=intensity
        )

        # C -> ((C ^ K) ^ K)
        def const_encode(match):
            val = match.group(0)
            if val.startswith("0x"):
                c = int(val, 16)
            else:
                c = int(val)
            k = random.randint(1, 0xFFFFFFFF)
            return f"(({c} ^ {k}) ^ {k})"

        # Find integer literals
        new_source = re.sub(r"\b\d+\b", const_encode, source_text, count=3)
        
        if new_source != source_text:
            res.changed_source = new_source
            res.compute_diff(source_text)
            res.success = True
        else:
            res.reason_if_failed = "No integer constants found"

        return res
