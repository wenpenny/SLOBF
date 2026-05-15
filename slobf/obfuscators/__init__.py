"""SLOBF obfuscation operators — AST-based, semantics-preserving."""

from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.obfuscators.opi import OPIObfuscator
from slobf.obfuscators.cff import CFFObfuscator
from slobf.obfuscators.er import ERObfuscator
from slobf.obfuscators.de import DEObfuscator
from slobf.obfuscators.jci import JCIObfuscator
from slobf.obfuscators.fs import FSObfuscator

__all__ = [
    "BaseObfuscator",
    "ObfuscationResult",
    "OPIObfuscator",
    "CFFObfuscator",
    "ERObfuscator",
    "DEObfuscator",
    "JCIObfuscator",
    "FSObfuscator",
]
