"""Base class and data structures for AST-based SLOBF obfuscators."""

from __future__ import annotations

import hashlib
import difflib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from tree_sitter import Node
from slobf.parser.c_parser import FunctionInfo


@dataclass
class ObfuscationResult:
    success: bool
    changed: bool
    operator_name: str
    function_id: str
    seed: int
    intensity: float
    changed_source: str | None = None
    inserted_lines: int = 0
    removed_lines: int = 0
    modified_lines: int = 0
    reason_if_failed: str | None = None
    source_hash_before: str | None = None
    source_hash_after: str | None = None
    diff: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_diff(self, original_source: str):
        if not self.changed_source or original_source == self.changed_source:
            self.changed = False
            return

        self.source_hash_before = hashlib.sha256(original_source.encode()).hexdigest()
        self.source_hash_after = hashlib.sha256(self.changed_source.encode()).hexdigest()

        diff_lines = list(difflib.unified_diff(
            original_source.splitlines(keepends=True),
            self.changed_source.splitlines(keepends=True),
            fromfile="original",
            tofile="obfuscated"
        ))
        self.diff = "".join(diff_lines)

        for line in diff_lines:
            if line.startswith("+") and not line.startswith("+++"):
                self.inserted_lines += 1
            elif line.startswith("-") and not line.startswith("---"):
                self.removed_lines += 1

        self.changed = self.source_hash_before != self.source_hash_after


class BaseObfuscator(ABC):
    """Abstract base for AST-based source-level obfuscation operators.

    Each operator works on a parsed C function and returns modified source text.
    Transformations use AST byte offsets for precise, semantics-preserving edits.
    """

    name: str

    def is_eligible(self, func_info: FunctionInfo) -> tuple[bool, str]:
        """Check if the function is eligible for this obfuscation.

        Override in subclasses for operator-specific rules.
        """
        if func_info.has_asm:
            return False, "Contains inline assembly"
        if func_info.is_variadic:
            return False, "Variadic function"
        return True, ""

    @abstractmethod
    def transform(self, source: bytes, func_node: Node, func_info: FunctionInfo,
                  seed: int, intensity: float) -> ObfuscationResult:
        """Apply obfuscation to the function, returning modified source and metadata."""
        ...
