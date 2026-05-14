"""Function Splitting (FS) — AST-based."""

import random
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.parser.c_parser import FunctionInfo
from tree_sitter import Node


class FSObfuscator(BaseObfuscator):
    name = "FS"

    def is_eligible(self, func_info: FunctionInfo) -> tuple[bool, str]:
        ok, reason = super().is_eligible(func_info)
        if not ok:
            return ok, reason
        if func_info.num_statements < 8:
            return False, "Too few statements for function splitting"
        if func_info.is_variadic:
            return False, "Variadic function"
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
        if len(stmts) < 6:
            res.reason_if_failed = "Too few body statements to split"
            return res

        # Find split point: prefer after a basic-block boundary, roughly at 40-60%
        split_ratio = 0.4 + rng.random() * 0.2
        split_idx = max(2, int(len(stmts) * split_ratio))

        # Move split point after a natural block boundary if possible
        split_types = {"if_statement", "for_statement", "while_statement",
                       "return_statement", "expression_statement"}
        for i in range(split_idx, min(split_idx + 4, len(stmts) - 2)):
            if stmts[i].type in split_types:
                # Check if next stmt starts a new logical block
                split_idx = i + 1
                break

        if split_idx >= len(stmts) - 2:
            split_idx = len(stmts) // 2

        # The first half stays in original; second half moves to helper
        first_half = stmts[:split_idx]
        second_half = stmts[split_idx:]

        # Collect local variables declared in the first half that are used in the second half
        # For simplicity: use a heuristic based on identifiers
        second_half_text = " ".join(
            source[s.start_byte:s.end_byte].decode("utf-8", errors="ignore")
            for s in second_half
        )
        first_half_text = " ".join(
            source[s.start_byte:s.end_byte].decode("utf-8", errors="ignore")
            for s in first_half
        )

        # Find local variable declarations in first half
        imported_vars = self._find_declared_vars(first_half, source)
        # Filter to only vars referenced in second half
        passed_vars = [v for v in imported_vars if v in second_half_text]

        helper_name = f"slobf_split_{rng.randint(1000, 9999)}"
        indent = " " * body.start_point[1]

        # Build helper function
        params = ", ".join(f"int {v}" for v in passed_vars)
        helper_sig = f"static void {helper_name}({params})"
        helper_lines = [helper_sig + " {"]
        for stmt in second_half:
            stmt_text = source[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="ignore")
            helper_lines.append(f"    {stmt_text}")
        helper_lines.append("}")

        # Build the modified original function: first_half + call to helper
        # Replace second_half with a call to helper + return if needed
        call_args = ", ".join(passed_vars) if passed_vars else ""
        call_stmt = f"{indent}    {helper_name}({call_args});"

        # Remove second_half from the body by splicing byte ranges
        # Take everything up to first_half[-1].end_byte, add call, then close
        last_first = first_half[-1]
        first_second = second_half[0]
        last_second = second_half[-1]

        # Build new function body interior
        closing_brace = None
        for child in body.children:
            if child.type == "}":
                closing_brace = child
                break

        if not closing_brace:
            res.reason_if_failed = "Cannot find closing brace"
            return res

        # New source = [prefix before body] + [helper func] + [new body] + [suffix after body]
        prefix = source[:func_node.start_byte]

        # Build new body: everything up to split point + call + closing
        body_interior = (
            source[body.children[0].end_byte:first_second.start_byte].decode("utf-8", errors="ignore") +
            call_stmt + "\n" +
            (" " * body.start_point[1]) +
            source[closing_brace.start_byte:closing_brace.end_byte].decode("utf-8", errors="ignore")
        )

        # Reconstruct: helper before the function, then modified function
        new_source = (
            prefix.decode("utf-8", errors="ignore") +
            "\n".join(helper_lines) + "\n\n" +
            source[func_node.start_byte:body.children[0].end_byte].decode("utf-8", errors="ignore") +
            "\n" + body_interior
        )

        res.changed_source = new_source
        res.compute_diff(source.decode("utf-8", errors="ignore"))
        res.success = True
        res.metadata["helper_name"] = helper_name
        res.metadata["split_point"] = split_idx
        res.metadata["passed_vars"] = passed_vars
        return res

    def _find_declared_vars(self, stmts: list[Node], source: bytes) -> list[str]:
        """Find variable names declared in the given statements."""
        vars_found = []
        for stmt in stmts:
            text = source[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="ignore")
            # Simple heuristic: look for declaration keywords followed by identifier
            if stmt.type == "declaration":
                decl_text = source[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="ignore")
                # Find identifiers after type specifiers
                self._extract_declared_names(stmt, source, vars_found)
        return list(set(vars_found))

    def _extract_declared_names(self, node: Node, source: bytes, names: list[str]):
        """Extract declarator names from a declaration node."""
        if node.type == "init_declarator":
            for child in node.children:
                if child.type == "identifier":
                    names.append(source[child.start_byte:child.end_byte].decode())
                elif child.type == "pointer_declarator":
                    for c in child.children:
                        if c.type == "identifier":
                            names.append(source[c.start_byte:c.end_byte].decode())
        for child in node.children:
            self._extract_declared_names(child, source, names)
