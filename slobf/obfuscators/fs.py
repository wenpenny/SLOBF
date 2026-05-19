"""Function Splitting (FS) — AST-based."""

import random
import re
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
        if func_info.num_returns > 1:
            return False, "Multiple return statements cannot be split"
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
                split_idx = i + 1
                break

        if split_idx >= len(stmts) - 2:
            split_idx = len(stmts) // 2

        first_half = stmts[:split_idx]
        second_half = stmts[split_idx:]

        # Check if a return statement is in the second half
        return_expr = None
        for i, stmt in enumerate(second_half):
            if stmt.type == "return_statement":
                ret_text = source[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="ignore")
                return_expr = ret_text[len("return"):].rstrip(";").strip()
                second_half = second_half[:i]
                break

        if len(second_half) < 2:
            res.reason_if_failed = "Second half too small after removing returns"
            return res

        # Extract function return type (skip storage class specifiers like "static")
        ret_type = "int"
        ret_type_parts = []
        for child in func_node.children:
            if child.type == "function_declarator":
                break
            if child.type in ("storage_class_specifier",):
                continue
            txt = source[child.start_byte:child.end_byte].decode("utf-8", errors="ignore").strip()
            if txt:
                ret_type_parts.append(txt)
        if ret_type_parts:
            ret_type = " ".join(ret_type_parts)

        second_half_text = " ".join(
            source[s.start_byte:s.end_byte].decode("utf-8", errors="ignore")
            for s in second_half
        )
        # Also include return expression text for variable detection
        if return_expr:
            second_half_text += " " + return_expr

        # Extract (name, type) for locally declared variables + function parameters
        imported_vars = self._find_declared_vars(first_half, source)
        imported_vars.extend(self._extract_params(func_node, source))
        # Use regex word-boundary matching to avoid substring false positives
        passed_vars = [
            (name, typ) for name, typ in imported_vars
            if re.search(r'\b' + re.escape(name) + r'\b', second_half_text)
        ]

        helper_name = f"slobf_split_{rng.randint(1000, 9999)}"
        indent = " " * body.start_point[1]

        # Build helper with correct types
        params = ", ".join(f"{typ} {name}" for name, typ in passed_vars)
        if return_expr:
            helper_sig = f"static {ret_type} {helper_name}({params})"
        else:
            helper_sig = f"static void {helper_name}({params})"
        helper_lines = [helper_sig + " {"]
        for stmt in second_half:
            stmt_text = source[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="ignore")
            helper_lines.append(f"    {stmt_text}")
        if return_expr:
            helper_lines.append(f"    return {return_expr};")
        helper_lines.append("}")

        call_args = ", ".join(name for name, _ in passed_vars) if passed_vars else ""
        if return_expr:
            call_stmt = f"{indent}    return {helper_name}({call_args});"
        else:
            call_stmt = f"{indent}    {helper_name}({call_args});"

        first_second = second_half[0]

        closing_brace = None
        for child in body.children:
            if child.type == "}":
                closing_brace = child
                break

        if not closing_brace:
            res.reason_if_failed = "Cannot find closing brace"
            return res

        prefix = source[:func_node.start_byte]
        suffix = source[func_node.end_byte:]

        body_interior = (
            source[body.children[0].end_byte:first_second.start_byte].decode("utf-8", errors="ignore") +
            call_stmt + "\n" +
            (" " * body.start_point[1]) +
            source[closing_brace.start_byte:closing_brace.end_byte].decode("utf-8", errors="ignore")
        )

        new_source = (
            prefix.decode("utf-8", errors="ignore") +
            "\n".join(helper_lines) + "\n\n" +
            source[func_node.start_byte:body.children[0].end_byte].decode("utf-8", errors="ignore") +
            "\n" + body_interior +
            suffix.decode("utf-8", errors="ignore")
        )

        res.changed_source = new_source
        res.compute_diff(source.decode("utf-8", errors="ignore"))
        res.success = True
        res.metadata["helper_name"] = helper_name
        res.metadata["split_point"] = split_idx
        res.metadata["passed_vars"] = [n for n, _ in passed_vars]
        return res

    def _find_declared_vars(self, stmts: list[Node], source: bytes) -> list[tuple[str, str]]:
        """Return list of (name, type_string) for locally declared variables."""
        results = []
        for stmt in stmts:
            if stmt.type == "declaration":
                # Find where the type specifier ends (before the first declarator)
                type_end = stmt.start_byte
                for child in stmt.children:
                    if child.type in ("init_declarator", "pointer_declarator",
                                      "array_declarator", "function_declarator",
                                      ",", ";"):
                        break
                    type_end = child.end_byte
                base_type = source[stmt.start_byte:type_end].decode().strip()
                self._extract_declared_vars(stmt, source, results, base_type, type_end)
        # Deduplicate by name (keep first occurrence)
        seen = set()
        unique = []
        for name, typ in results:
            if name not in seen:
                seen.add(name)
                unique.append((name, typ))
        return unique

    def _extract_declared_vars(self, node: Node, source: bytes,
                               results: list[tuple[str, str]],
                               base_type: str, type_end: int):
        """Extract (name, type_string) from declaration subtrees.

        Uses pre-computed base_type to avoid multi-declarator contamination
        (e.g., ``int a, b`` would previously extract ``int a, `` as b's type).
        """
        if node.type == "init_declarator":
            name = None
            ptr_depth = ""
            for child in node.children:
                if child.type == "identifier":
                    name = source[child.start_byte:child.end_byte].decode()
                elif child.type == "pointer_declarator":
                    ptr_depth = self._count_ptr_stars(child, source)
                    name = self._find_identifier(child, source)
                elif child.type == "array_declarator":
                    name = self._find_identifier(child, source)
            if name:
                full_type = (base_type + " " + ptr_depth).strip() if ptr_depth else base_type
                results.append((name, full_type))
        elif node.type in ("pointer_declarator", "array_declarator"):
            # Direct child of declaration (e.g., ``struct hash_entry *bucket;``)
            name = self._find_identifier(node, source)
            if name:
                ptr = self._count_ptr_stars(node, source) if node.type == "pointer_declarator" else ""
                full_type = (base_type + " " + ptr).strip() if ptr else base_type
                results.append((name, full_type))
        for child in node.children:
            self._extract_declared_vars(child, source, results, base_type, type_end)

    @staticmethod
    def _count_ptr_stars(node: Node, source: bytes) -> str:
        """Count pointer indirection levels, e.g. ``*`` or ``**``."""
        stars = ""
        for child in node.children:
            if child.type == "pointer_declarator":
                stars += "*" + FSObfuscator._count_ptr_stars(child, source)
            elif child.type == "*":
                stars += "*"
        if node.type == "pointer_declarator" and not stars:
            stars = "*"
        return stars

    @staticmethod
    def _find_identifier(node: Node, source: bytes) -> str | None:
        """Find the first identifier descendant in a declarator node."""
        if node.type == "identifier":
            return source[node.start_byte:node.end_byte].decode()
        for child in node.children:
            result = FSObfuscator._find_identifier(child, source)
            if result:
                return result
        return None

    @staticmethod
    def _extract_params(func_node: Node, source: bytes) -> list[tuple[str, str]]:
        """Extract (name, type) from function parameters."""
        params = []
        for child in func_node.children:
            if child.type == "function_declarator":
                for dc in child.children:
                    if dc.type == "parameter_list":
                        for pc in dc.children:
                            if pc.type == "parameter_declaration":
                                # Find the identifier in the parameter declaration
                                identifier = None
                                for n in pc.children:
                                    if n.type == "identifier":
                                        identifier = n
                                        break
                                    elif n.type in ("pointer_declarator", "array_declarator"):
                                        for cn in n.children:
                                            if cn.type == "identifier":
                                                identifier = cn
                                                break
                                if identifier:
                                    name = source[identifier.start_byte:identifier.end_byte].decode()
                                    type_text = source[pc.start_byte:identifier.start_byte].decode().strip()
                                    params.append((name, type_text))
        return params
