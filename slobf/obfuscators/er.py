"""Expression Rewriting (ER) — AST-based.

Implements algebraic expression rewriting (Collberg et al., "Breaking Abstractions"):
- Replace arithmetic expressions with semantically equivalent forms.
- Uses tree-sitter AST to locate binary_expression and unary_expression nodes.
- All rewrites are mathematically identity-preserving.
"""

from __future__ import annotations

import random
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.parser.c_parser import FunctionInfo
from tree_sitter import Node

# ---------------------------------------------------------------------------
# Rewrite rule tables — each rule maps an operator to a list of
# (priority, template_fn) pairs where higher priority = apply first.
# ---------------------------------------------------------------------------


class ERObfuscator(BaseObfuscator):
    name = "ER"

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

        # Collect candidate nodes
        candidates = self._collect_expr_nodes(func_node)
        if not candidates:
            res.reason_if_failed = "No expressions to rewrite"
            return res

        rng.shuffle(candidates)
        num_rewrites = max(1, int(len(candidates) * min(intensity, 1.0)))
        targets = candidates[:num_rewrites]

        new_source = source
        for node in sorted(targets, key=lambda n: n.start_byte, reverse=True):
            rewritten = self._rewrite_node(node, new_source, rng)
            if rewritten is not None:
                new_source = (new_source[:node.start_byte] +
                              rewritten.encode() +
                              new_source[node.end_byte:])

        if new_source == source:
            res.reason_if_failed = "No expressions matched rewriting rules"
            return res

        res.changed_source = new_source.decode("utf-8", errors="ignore")
        res.compute_diff(source.decode("utf-8", errors="ignore"))
        res.success = True
        res.metadata["expressions_rewritten"] = num_rewrites
        return res

    # ------------------------------------------------------------------
    # AST collection
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_expr_nodes(root: Node) -> list[Node]:
        results = []
        if root.type in ("binary_expression", "unary_expression", "update_expression",
                         "parenthesized_expression"):
            results.append(root)
        for child in root.children:
            results.extend(ERObfuscator._collect_expr_nodes(child))
        return results

    # ------------------------------------------------------------------
    # Rewrite dispatch
    # ------------------------------------------------------------------

    def _rewrite_node(self, node: Node, source: bytes, rng: random.Random) -> str | None:
        if node.type == "binary_expression":
            return self._rewrite_binary(node, source, rng)
        elif node.type == "unary_expression":
            return self._rewrite_unary(node, source, rng)
        elif node.type == "update_expression":
            return self._rewrite_update(node, source, rng)
        elif node.type == "parenthesized_expression":
            return self._rewrite_paren(node, source, rng)
        return None

    # ------------------------------------------------------------------
    # Binary expression rewrites
    # ------------------------------------------------------------------

    def _rewrite_binary(self, node: Node, source: bytes, rng: random.Random) -> str | None:
        children = node.children
        op_node = None
        for c in children:
            if c.type in self._ALL_BINARY_OPS:
                op_node = c
                break
        if not op_node:
            return None

        parts = [c for c in children if c != op_node]
        if len(parts) < 2:
            return None

        left = self._node_text(parts[0], source)
        right = self._node_text(parts[1], source)
        op = self._node_text(op_node, source)

        rules = self._BINARY_RULES.get(op, [])
        if not rules:
            return None

        # Pick a random applicable rule
        rng.shuffle(rules)
        for rule_fn in rules:
            result = rule_fn(left, right, rng)
            if result is not None:
                return result
        return None

    _ALL_BINARY_OPS = {
        "+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>",
        "==", "!=", "<", ">", "<=", ">=", "&&", "||",
    }

    @staticmethod
    def _node_text(node: Node, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

    # ------------------------------------------------------------------
    # Rule definitions
    # Each function: (left_str, right_str, rng) -> str | None
    # ------------------------------------------------------------------

    _BINARY_RULES = {
        # Addition
        "+": [
            lambda l, r, _: f"({l} - (-({r})))",
            lambda l, r, _: f"(({l} + {r}) - ({l} & {r}) + ({l} & {r}))",
        ],
        # Subtraction
        "-": [
            lambda l, r, _: f"({l} + (-({r})))",
            lambda l, r, _: f"(({l} - {r}) + ({l} ^ {r}) - ({l} ^ {r}))",
        ],
        # Multiplication
        "*": [
            lambda l, r, _: f"(({l} + {l}) * ({r} / 2))" if ERObfuscator._is_int2(r) else None,
            lambda l, r, _: f"(({l} << 1) * {r})" if ERObfuscator._is_int(r, "2") else f"(({r} << 1) * {l})" if ERObfuscator._is_int(l, "2") else None,
            lambda l, r, _: f"(({l} << 1) * ({r} / 2))" if ERObfuscator._is_int2(r) else None,
        ],
        # Division by 2 → right shift (unsigned)
        "/": [
            lambda l, r, _: f"((unsigned)({l}) >> 1)" if ERObfuscator._is_int(r, "2") else None,
            lambda l, r, _: f"(({l}) / ({r}))",
        ],
        # Bitwise AND
        "&": [
            lambda l, r, _: f"(({l} | {r}) - ({l} ^ {r}))",
            lambda l, r, _: f"~((~({l})) | (~({r})))",
        ],
        # Bitwise OR
        "|": [
            lambda l, r, _: f"(({l} & {r}) + ({l} ^ {r}))",
            lambda l, r, _: f"~((~({l})) & (~({r})))",
        ],
        # Bitwise XOR
        "^": [
            lambda l, r, _: f"(({l} | {r}) - ({l} & {r}))",
            lambda l, r, _: f"(({l} & ~({r})) | (~({l}) & {r}))",
        ],
        # Left shift (X << 1 → X * 2, X << C → ...)
        "<<": [
            lambda l, r, _: f"({l} * 2)" if ERObfuscator._is_int(r, "1") else None,
            lambda l, r, _: f"({l} + {l})" if ERObfuscator._is_int(r, "1") else None,
        ],
        # Right shift
        ">>": [
            lambda l, r, _: f"((unsigned)({l}) / 2)" if ERObfuscator._is_int(r, "1") else None,
        ],
        # Logical AND
        "&&": [
            lambda l, r, _: f"(!(!({l}) || !({r})))",
            lambda l, r, _: f"((int)({l}) & (int)({r}))",
        ],
        # Logical OR
        "||": [
            lambda l, r, _: f"(!(!({l}) && !({r})))",
            lambda l, r, _: f"((int)({l}) | (int)({r}))",
        ],
        # Equality
        "==": [
            lambda l, r, _: f"(!(({l}) != ({r})))",
            lambda l, r, _: f"((({l}) ^ ({r})) == 0)",
        ],
        "!=": [
            lambda l, r, _: f"(!(({l}) == ({r})))",
            lambda l, r, _: f"((({l}) ^ ({r})) != 0)",
        ],
    }

    @staticmethod
    def _is_int(text: str, expected: str) -> bool:
        return text.strip() == expected

    @staticmethod
    def _is_int2(text: str) -> bool:
        return text.strip() == "2"

    # ------------------------------------------------------------------
    # Unary expression rewrites
    # ------------------------------------------------------------------

    def _rewrite_unary(self, node: Node, source: bytes, rng: random.Random) -> str | None:
        op = None
        operand = None
        for c in node.children:
            if c.type in ("!", "~", "-"):
                op = self._node_text(c, source)
            elif c.type not in ("(", ")"):
                operand = c
        if not op or not operand:
            return None
        operand_text = self._node_text(operand, source)

        rules = {
            "!": [
                f"({operand_text} == 0)",
                f"(({operand_text}) ? 0 : 1)",
            ],
            "~": [
                f"({operand_text} ^ 0xFFFFFFFF)",
                f"(({operand_text} | 0xFFFFFFFF) ^ ({operand_text} & 0))",
            ],
            "-": [
                f"({operand_text} ^ 0x80000000) + 0x80000000",
                f"(0 - ({operand_text}))",
            ],
        }
        options = rules.get(op, [])
        if not options:
            return None
        return rng.choice(options)

    # ------------------------------------------------------------------
    # Update expression rewrites (i++, i--, ++i, --i)
    # ------------------------------------------------------------------

    def _rewrite_update(self, node: Node, source: bytes, rng: random.Random) -> str | None:
        text = self._node_text(node, source)
        # i++  →  (i += 1)
        # i--  →  (i -= 1)
        if text.endswith("++"):
            return f"({text[:-2]} += 1)"
        elif text.endswith("--"):
            return f"({text[:-2]} -= 1)"
        elif text.startswith("++"):
            return f"({text[2:]} += 1)"
        elif text.startswith("--"):
            return f"({text[2:]} -= 1)"
        return None

    # ------------------------------------------------------------------
    # Parenthesized expression — strip redundant parens or add extra
    # ------------------------------------------------------------------

    def _rewrite_paren(self, node: Node, source: bytes, rng: random.Random) -> str | None:
        inner = None
        for c in node.children:
            if c.type not in ("(", ")"):
                inner = c
                break
        if inner:
            # Add extra redundant parentheses layer
            inner_text = self._node_text(inner, source)
            return f"(({inner_text}))"
        return None
