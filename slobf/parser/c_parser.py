"""C source code parser using tree-sitter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node


@dataclass
class FunctionInfo:
    dataset: str
    source_file: str
    name: str
    start_line: int
    end_line: int
    num_lines: int
    num_statements: int = 0
    num_branches: int = 0
    num_loops: int = 0
    num_returns: int = 0
    is_static: bool = False
    is_inline: bool = False
    is_variadic: bool = False
    has_goto: bool = False
    has_switch: bool = False
    has_asm: bool = False
    has_macro_heavy: bool = False
    has_pointer_ops: bool = False
    has_float_ops: bool = False
    eligibility: dict[str, bool] = field(default_factory=dict)
    ineligible_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        return d


class CParser:
    def __init__(self):
        self.language = Language(tsc.language())
        self.parser = Parser(self.language)

    def parse_file(self, file_path: Path, dataset_name: str) -> list[FunctionInfo]:
        """Extract functions from a C source file."""
        if not file_path.exists():
            return []

        try:
            content = file_path.read_bytes()
            tree = self.parser.parse(content)
        except Exception:
            return []

        functions = []
        root_node = tree.root_node
        self._find_functions(root_node, content, file_path, dataset_name, functions)
        return functions

    def _find_functions(self, node: Node, content: bytes, file_path: Path, 
                        dataset_name: str, functions: list[FunctionInfo]):
        """Recursively find function definitions."""
        if node.type == "function_definition":
            func_info = self._extract_function_info(node, content, file_path, dataset_name)
            if func_info:
                functions.append(func_info)
        
        for child in node.children:
            self._find_functions(child, content, file_path, dataset_name, functions)

    def _extract_function_info(self, node: Node, content: bytes, 
                               file_path: Path, dataset_name: str) -> FunctionInfo | None:
        """Extract detailed information from a function definition node."""
        # Find declarator and name
        declarator = None
        for child in node.children:
            if child.type == "function_declarator":
                declarator = child
                break
        
        if not declarator:
            return None

        # Find name
        name_node = None
        # Simplified name finding; tree-sitter-c structure can vary
        def find_name(n):
            if n.type == "identifier": return n
            for c in n.children:
                res = find_name(c)
                if res: return res
            return None
        
        name_node = find_name(declarator)
        if not name_node:
            return None
        
        name = content[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")

        # Basic stats
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        num_lines = end_line - start_line + 1

        info = FunctionInfo(
            dataset=dataset_name,
            source_file=str(file_path),
            name=name,
            start_line=start_line,
            end_line=end_line,
            num_lines=num_lines,
        )

        # Modifiers
        parent = node.parent
        # Look at storage class specifiers etc in the same definition
        for child in node.children:
            if child.type == "storage_class_specifier":
                txt = content[child.start_byte:child.end_byte].decode()
                if txt == "static": info.is_static = True
            if child.type == "type_qualifier":
                txt = content[child.start_byte:child.end_byte].decode()
                if txt == "inline": info.is_inline = True

        # Body analysis
        body = None
        for child in node.children:
            if child.type == "compound_statement":
                body = child
                break
        
        if body:
            self._analyze_body(body, content, info)
            # Adjust num_statements: compound_statement itself shouldn't count
            # but we want to count statements inside it.
        else:
            # Check if it's just a semicolon (declaration)
            is_decl = True
            for child in node.children:
                if child.type == "compound_statement":
                    is_decl = False
                    break
            if is_decl:
                info.ineligible_reason = "Function declaration, no body"
                info.eligibility = {"general": False}
        
        # Check variadic
        for child in declarator.children:
            if child.type == "parameters":
                for p in child.children:
                    if p.type == "...":
                        info.is_variadic = True
                        break

        return info

    def _analyze_body(self, node: Node, content: bytes, info: FunctionInfo):
        """Walk the function body to gather stats and features."""
        
        # Stats to collect
        node_type = node.type
        if node_type in ("expression_statement", "declaration"):
            info.num_statements += 1
        elif node_type in ("if_statement", "switch_statement"):
            info.num_branches += 1
            if node_type == "switch_statement": info.has_switch = True
        elif node_type in ("while_statement", "for_statement", "do_statement"):
            info.num_loops += 1
        elif node_type == "return_statement":
            info.num_returns += 1
        elif node_type == "goto_statement":
            info.has_goto = True
        elif node_type == "asm_statement":
            info.has_asm = True
        
        # Pointer operations
        if node_type in ("pointer_expression", "field_expression"):
            info.has_pointer_ops = True
        
        # Floating point - very simple heuristic: look for float/double keywords or literals
        if node_type in ("primitive_type", "floating_point_literal"):
            txt = content[node.start_byte:node.end_byte].decode(errors="ignore")
            if txt in ("float", "double") or node_type == "floating_point_literal":
                info.has_float_ops = True

        for child in node.children:
            self._analyze_body(child, content, info)
