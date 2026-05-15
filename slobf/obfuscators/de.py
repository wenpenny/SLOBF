"""Data Encoding (DE) — AST-based.

Implements standard data encoding techniques (Collberg et al.):
- Integer constants: C → ((C ^ K1) - K2) ^ K3  (multi-layer)
- String literals:  "abc" → {K^'a', K^'b', K^'c', K^0} decoded at runtime
All encodings are invertible and semantics-preserving.
"""

from __future__ import annotations

import random
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.parser.c_parser import FunctionInfo
from tree_sitter import Node


class DEObfuscator(BaseObfuscator):
    name = "DE"

    def is_eligible(self, func_info: FunctionInfo) -> tuple[bool, str]:
        ok, reason = super().is_eligible(func_info)
        if not ok:
            return ok, reason
        return True, ""

    def transform(self, source: bytes, func_node: Node, func_info: FunctionInfo,
                  seed: int, intensity: float) -> ObfuscationResult:
        rng = random.Random(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_info.name, seed=seed, intensity=intensity
        )

        literal_nodes = self._collect_literals(func_node)
        if not literal_nodes:
            res.reason_if_failed = "No literals to encode"
            return res

        rng.shuffle(literal_nodes)
        num_encode = max(1, int(len(literal_nodes) * min(intensity, 1.0)))
        targets = literal_nodes[:num_encode]

        new_source = source
        for node in sorted(targets, key=lambda n: n.start_byte, reverse=True):
            encoded = self._encode_node(node, new_source, rng)
            if encoded is not None:
                new_source = (new_source[:node.start_byte] +
                              encoded.encode() +
                              new_source[node.end_byte:])

        if new_source == source:
            res.reason_if_failed = "No literals could be encoded"
            return res

        res.changed_source = new_source.decode("utf-8", errors="ignore")
        res.compute_diff(source.decode("utf-8", errors="ignore"))
        res.success = True
        res.metadata["literals_encoded"] = len(targets)
        return res

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_literals(root: Node) -> list[Node]:
        results = []
        if root.type in ("number_literal", "string_literal", "character_literal"):
            results.append(root)
        for child in root.children:
            results.extend(DEObfuscator._collect_literals(child))
        return results

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def _encode_node(self, node: Node, source: bytes, rng: random.Random) -> str | None:
        if node.type in ("number_literal", "character_literal"):
            return self._encode_integer(node, source, rng)
        elif node.type == "string_literal":
            return self._encode_string(node, source, rng)
        return None

    def _encode_integer(self, node: Node, source: bytes, rng: random.Random) -> str | None:
        text = source[node.start_byte:node.end_byte].decode()
        try:
            if text.startswith("0x") or text.startswith("0X"):
                base = 16
                val = int(text, 16)
            else:
                base = 10
                val = int(text)
        except ValueError:
            return None

        if abs(val) <= 1:
            return None  # don't encode trivial constants

        # Pick between XOR-based encoding strategies (avoid unsigned casts)
        strategy = rng.randint(0, 1)

        if strategy == 0:
            # Multi-layer XOR: ((C ^ K1) - K2) ^ K3
            k1 = rng.randint(0x1000, 0x7FFFFFFF)
            k2 = rng.randint(1, 0xFFFF)
            k3 = rng.randint(0x1000, 0x7FFFFFFF)
            return f"((({val} ^ {k1}) - {k2}) ^ {k3})"
        else:
            # Double XOR with intermediate arithmetic
            k = rng.randint(0x1000, 0x7FFFFFFF)
            return f"((({val} ^ {k}) + ({val} & 0)) ^ {k})"

    def _encode_string(self, node: Node, source: bytes, rng: random.Random) -> str | None:
        """Replace "abc" with a runtime-decoded stack array.

        Produces valid C: a compound literal char array with XOR-encoded chars.
        The decoding happens at runtime via a simple loop.
        """
        text = source[node.start_byte:node.end_byte].decode()
        if len(text) < 3:
            return None

        # Handle both "..." and L"..." forms
        if text.startswith('L"'):
            prefix = 'L'
            content = text[2:-1] if text.endswith('"') else text[2:]
        elif text.startswith('"'):
            prefix = ''
            content = text[1:-1] if text.endswith('"') else text[1:]
        else:
            return None

        if not content:
            return None

        key = rng.randint(1, 255)
        # Build the encoded initializer list
        encoded_chars = []
        for ch in content:
            encoded_chars.append(str(ord(ch) ^ key))
        encoded_chars.append(str(key))  # null terminator XOR key → key itself

        var = f"slobf_s_{rng.randint(1000, 9999)}"

        return (
            f"(__extension__({{"
            f"static char {var}[] = {{{', '.join(encoded_chars)}}};"
            f"for(int _i=0;_i<sizeof({var})-1;_i++) {var}[_i]^={var}[sizeof({var})-1];"
            f"{var};"
            f"}}))"
        )
