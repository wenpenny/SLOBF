"""Base class and data structures for SLOBF obfuscators."""

from __future__ import annotations

import hashlib
import difflib
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from tree_sitter import Node


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
        
        # Simple line counts from diff
        for line in diff_lines:
            if line.startswith("+") and not line.startswith("+++"):
                self.inserted_lines += 1
            elif line.startswith("-") and not line.startswith("---"):
                self.removed_lines += 1
        
        self.changed = self.source_hash_before != self.source_hash_after


@runtime_checkable
class BaseObfuscator(Protocol):
    name: str

    def is_eligible(self, node: Node, func_meta: dict[str, Any]) -> tuple[bool, str]:
        """Check if the function is eligible for this obfuscation."""
        ...

    def transform(self, source_text: str, node: Node, func_meta: dict[str, Any], 
                  seed: int, intensity: float) -> ObfuscationResult:
        """Apply the transformation to the function source."""
        ...
