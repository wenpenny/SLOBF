"""C source code parser using tree-sitter with AST utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node


@dataclass
class FunctionInfo:
    dataset: str = ""
    program: str = ""
    source_file: str = ""
    name: str = ""
    start_line: int = 0
    end_line: int = 0
    start_byte: int = 0
    end_byte: int = 0
    num_lines: int = 0
    num_statements: int = 0
    num_branches: int = 0
    num_loops: int = 0
    num_returns: int = 0
    is_static: bool = False
    is_inline: bool = False
    is_variadic: bool = False
    has_goto: bool = False
    has_switch: bool = False
    has_break: bool = False
    has_continue: bool = False
    has_asm: bool = False
    has_pointer_ops: bool = False
    has_float_ops: bool = False
    return_type: str = ""
    param_types: list[str] = field(default_factory=list)
    eligibility: dict[str, bool] = field(default_factory=dict)
    ineligible_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class CParser:
    def __init__(self):
        self.language = Language(tsc.language())
        self.parser = Parser(self.language)

    def parse_bytes(self, source: bytes) -> Node:
        """Parse source bytes, return root AST node."""
        return self.parser.parse(source).root_node

    def parse_file(self, file_path: Path, dataset_name: str = "", program_name: str = "") -> list[FunctionInfo]:
        if not file_path.exists():
            return []

        try:
            content = file_path.read_bytes()
        except Exception:
            return []

        try:
            tree = self.parser.parse(content)
        except Exception:
            return []

        functions = []
        self._find_functions(tree.root_node, content, file_path, dataset_name, program_name, functions)
        return functions

    def find_function_node(self, root: Node, func_name: str, source: bytes) -> Node | None:
        """Find a function_definition node by name within an AST."""
        for child in root.children:
            if child.type == "function_definition":
                declarator = self._find_deep_child(child, "function_declarator")
                if declarator:
                    name_node = self._find_identifier(declarator)
                    if name_node:
                        name = source[name_node.start_byte:name_node.end_byte].decode()
                        if name == func_name:
                            return child
            result = self.find_function_node(child, func_name, source)
            if result:
                return result
        return None

    # ------------------------------------------------------------------
    # AST query helpers
    # ------------------------------------------------------------------

    def get_function_body(self, func_node: Node) -> Node | None:
        """Return the compound_statement body of a function_definition."""
        return self._find_deep_child(func_node, "compound_statement")

    def get_body_statements(self, body_node: Node) -> list[Node]:
        """Return top-level statements inside a compound_statement, skipping '{' and '}'."""
        stmts = []
        for child in body_node.children:
            if child.type not in ("{", "}"):
                stmts.append(child)
        return stmts

    def collect_basic_blocks(self, body_node: Node) -> list[list[Node]]:
        """Split body statements into basic blocks at branch/jump boundaries.

        A new block starts after: if/for/while/do/switch/return/goto/break/continue.
        """
        stmts = self.get_body_statements(body_node)
        blocks = []
        current = []
        split_types = {"if_statement", "for_statement", "while_statement",
                       "do_statement", "switch_statement", "return_statement",
                       "goto_statement", "break_statement", "continue_statement",
                       "labeled_statement"}
        for s in stmts:
            if current and s.type in split_types:
                blocks.append(current)
                current = []
            current.append(s)
        if current:
            blocks.append(current)
        return blocks

    def collect_nodes_of_type(self, root: Node, target_types: set[str]) -> list[Node]:
        """Collect all descendant nodes matching target_types."""
        results = []
        if root.type in target_types:
            results.append(root)
        for child in root.children:
            results.extend(self.collect_nodes_of_type(child, target_types))
        return results

    def get_node_text(self, node: Node, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

    def replace_node_text(self, source: bytes, old_node: Node, new_text: str) -> bytes:
        """Replace the text of old_node with new_text using byte offsets."""
        return source[:old_node.start_byte] + new_text.encode() + source[old_node.end_byte:]

    def replace_range(self, source: bytes, start_byte: int, end_byte: int, new_text: str) -> bytes:
        return source[:start_byte] + new_text.encode() + source[end_byte:]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _child_of_type(self, node: Node, type_name: str) -> Node | None:
        for c in node.children:
            if c.type == type_name:
                return c
        return None

    def _find_deep_child(self, node: Node, type_name: str) -> Node | None:
        """Find a descendant node of the given type (recursive)."""
        if node.type == type_name:
            return node
        for c in node.children:
            r = self._find_deep_child(c, type_name)
            if r:
                return r
        return None

    def _find_identifier(self, node: Node) -> Node | None:
        if node.type == "identifier":
            return node
        for c in node.children:
            r = self._find_identifier(c)
            if r:
                return r
        return None

    def _find_functions(self, node: Node, content: bytes, file_path: Path,
                        dataset_name: str, program_name: str, functions: list[FunctionInfo]):
        stack = [node]
        while stack:
            n = stack.pop()
            if n.type == "function_definition":
                info = self._extract_function_info(n, content, file_path, dataset_name, program_name)
                if info:
                    functions.append(info)
            stack.extend(n.children)

    def _extract_function_info(self, node: Node, content: bytes,
                                file_path: Path, dataset_name: str, program_name: str) -> FunctionInfo | None:
        declarator = self._find_deep_child(node, "function_declarator")
        if not declarator:
            return None

        name_node = self._find_identifier(declarator)
        if not name_node:
            return None

        name = content[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")

        info = FunctionInfo(
            dataset=dataset_name,
            program=program_name,
            source_file=str(file_path),
            name=name,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            num_lines=node.end_point[0] - node.start_point[0] + 1,
        )

        # Storage class / qualifiers
        for child in node.children:
            if child.type == "storage_class_specifier":
                txt = content[child.start_byte:child.end_byte].decode()
                if txt == "static":
                    info.is_static = True
            if child.type == "type_qualifier":
                txt = content[child.start_byte:child.end_byte].decode()
                if txt == "inline":
                    info.is_inline = True

        # Return type
        ret_type_node = None
        for child in node.children:
            if child.type != "function_declarator" and child.type != "compound_statement":
                ret_type_node = child
                break
        if ret_type_node:
            info.return_type = content[ret_type_node.start_byte:ret_type_node.end_byte].decode()

        # Parameter types
        for child in declarator.children:
            if child.type == "parameter_list":
                for pc in child.children:
                    if pc.type == "parameter_declaration":
                        info.param_types.append(content[pc.start_byte:pc.end_byte].decode())

        # Variadic
        for child in declarator.children:
            if child.type == "parameters":
                for p in child.children:
                    if p.type == "...":
                        info.is_variadic = True

        # Body analysis
        body = self._child_of_type(node, "compound_statement")
        if body:
            self._analyze_body(body, content, info)
        else:
            # Declaration only, no body
            info.ineligible_reason = "Function declaration, no body"
            info.eligibility = {"general": False}

        return info

    def _analyze_body(self, node: Node, content: bytes, info: FunctionInfo):
        t = node.type
        if t in ("expression_statement", "declaration"):
            info.num_statements += 1
        elif t in ("if_statement", "switch_statement"):
            info.num_branches += 1
            if t == "switch_statement":
                info.has_switch = True
        elif t in ("while_statement", "for_statement", "do_statement"):
            info.num_loops += 1
        elif t == "return_statement":
            info.num_returns += 1
        elif t == "goto_statement":
            info.has_goto = True
        elif t == "break_statement":
            info.has_break = True
        elif t == "continue_statement":
            info.has_continue = True
        elif t == "asm_statement":
            info.has_asm = True
        if t in ("pointer_expression", "field_expression", "subscript_expression"):
            info.has_pointer_ops = True
        if t in ("primitive_type", "float_literal"):
            txt = content[node.start_byte:node.end_byte].decode(errors="ignore").strip()
            if txt in ("float", "double") or t == "float_literal":
                info.has_float_ops = True

        for child in node.children:
            self._analyze_body(child, content, info)
