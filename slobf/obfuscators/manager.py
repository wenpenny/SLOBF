"""Manager for applying AST-based obfuscation operators in-place."""

from __future__ import annotations

import logging
from pathlib import Path

from slobf.config import SlobfConfig
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.obfuscators.opi import OPIObfuscator
from slobf.obfuscators.cff import CFFObfuscator
from slobf.obfuscators.er import ERObfuscator
from slobf.obfuscators.de import DEObfuscator
from slobf.obfuscators.jci import JCIObfuscator
from slobf.obfuscators.fs import FSObfuscator
from slobf.parser.c_parser import CParser, FunctionInfo

logger = logging.getLogger(__name__)


class ObfuscationManager:
    """Applies obfuscation operators by modifying function source in-place."""

    def __init__(self, cfg: SlobfConfig):
        self.cfg = cfg
        self.parser = CParser()
        self.operators: dict[str, BaseObfuscator] = {
            "OPI": OPIObfuscator(),
            "CFF": CFFObfuscator(),
            "ER": ERObfuscator(),
            "DE": DEObfuscator(),
            "JCI": JCIObfuscator(),
            "FS": FSObfuscator(),
        }

    def get_operator(self, name: str) -> BaseObfuscator | None:
        return self.operators.get(name)

    def obfuscate_function_in_file(
        self,
        source_path: Path,
        func_info: FunctionInfo,
        operator_name: str,
        seed: int = 0,
        intensity: float = 1.0,
    ) -> ObfuscationResult | None:
        """Apply an obfuscation operator to a function in its source file.

        Returns a result with the full modified file content in changed_source,
        or None if the operator doesn't exist.
        """
        operator = self.operators.get(operator_name)
        if operator is None:
            logger.warning("Unknown operator: %s", operator_name)
            return None

        source = source_path.read_bytes()

        # Find the target function node
        root = self.parser.parse_bytes(source)
        func_node = self.parser.find_function_node(root, func_info.name, source)
        if func_node is None:
            logger.warning("Function %s not found in %s", func_info.name, source_path)
            return None

        # Check eligibility
        eligible, reason = operator.is_eligible(func_info)
        if not eligible:
            logger.debug("Function %s ineligible for %s: %s", func_info.name, operator_name, reason)
            return None

        # Apply transformation
        logger.info("Applying %s to %s::%s", operator_name, source_path.name, func_info.name)
        result = operator.transform(source, func_node, func_info, seed, intensity)

        # Store the full file source in changed_source so compiler can use it
        if result.success and result.changed_source:
            result.metadata["source_file"] = str(source_path)
            result.metadata["function_name"] = func_info.name

        return result
