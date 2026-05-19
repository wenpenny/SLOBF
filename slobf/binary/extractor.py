"""Binary function extraction from ELF binaries."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

logger = logging.getLogger(__name__)


@dataclass
class BinaryFunction:
    name: str
    address: int
    size: int
    disassembly: list[str] = field(default_factory=list)
    opcodes: list[str] = field(default_factory=list)
    bytes_hex: str = ""
    bb_count: int = 0
    instruction_count: int = 0
    opt: str = ""
    operator: str | None = None
    seed: int | None = None
    dataset: str = ""
    program: str = ""

    def compute_hashes(self) -> dict[str, str]:
        return {
            "instruction_hash": hashlib.sha256(
                "\n".join(self.disassembly).encode()
            ).hexdigest(),
            "opcode_hash": hashlib.sha256(
                " ".join(self.opcodes).encode()
            ).hexdigest(),
            "byte_hash": hashlib.sha256(self.bytes_hex.encode()).hexdigest(),
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d.update(self.compute_hashes())
        return d


class BinaryExtractor:
    """Extracts functions from full-program ELF binaries."""

    def __init__(self, arch=CS_ARCH_X86, mode=CS_MODE_64):
        self.md = Cs(arch, mode)

    def extract_function(
        self, binary_path: Path, func_name: str,
        opt: str = "O0", operator: str | None = None, seed: int | None = None,
    ) -> BinaryFunction | None:
        """Extract a named function from an ELF binary."""
        if not binary_path.exists():
            logger.warning("Binary not found: %s", binary_path)
            return None

        try:
            with binary_path.open("rb") as f:
                elf = ELFFile(f)
                symtab = elf.get_section_by_name(".symtab")
                if not symtab:
                    symtab = elf.get_section_by_name(".dynsym")
                if not symtab:
                    logger.warning("No symbol table in %s", binary_path)
                    return None

                symbol = None
                for s in symtab.iter_symbols():
                    if s.name == func_name:
                        symbol = s
                        break

                if not symbol:
                    logger.debug("Symbol %s not found in %s", func_name, binary_path.name)
                    return None

                addr = symbol["st_value"]
                size = symbol["st_size"]
                if size == 0:
                    logger.debug("Symbol %s has zero size (possibly inlined)", func_name)
                    return None

                # Locate the section
                section = None
                for s in elf.iter_sections():
                    if s["sh_addr"] <= addr < s["sh_addr"] + s["sh_size"]:
                        section = s
                        break

                if not section:
                    logger.warning("Section for %s @0x%x not found", func_name, addr)
                    return None

                offset = addr - section["sh_addr"]
                raw_bytes = section.data()[offset:offset + size]

                disasm = []
                opcodes = []
                instr_count = 0
                bb_count = 1

                for i in self.md.disasm(raw_bytes, addr):
                    disasm.append(f"0x{i.address:x}:\t{i.mnemonic}\t{i.op_str}")
                    opcodes.append(i.mnemonic)
                    instr_count += 1
                    if i.mnemonic in (
                        "jmp", "je", "jne", "jg", "jl", "ja", "jb",
                        "jge", "jle", "jae", "jbe", "ret",
                    ):
                        bb_count += 1

                return BinaryFunction(
                    name=func_name,
                    address=addr,
                    size=size,
                    disassembly=disasm,
                    opcodes=opcodes,
                    bytes_hex=raw_bytes.hex(),
                    bb_count=bb_count,
                    instruction_count=instr_count,
                    opt=opt,
                    operator=operator,
                    seed=seed,
                )
        except Exception as e:
            logger.error("Extraction error for %s in %s: %s", func_name, binary_path, e)
            return None

    def extract_and_save(
        self,
        binary_path: Path,
        func_name: str,
        output_dir: Path,
        opt: str = "O0",
        operator: str | None = None,
        seed: int | None = None,
    ) -> BinaryFunction | None:
        """Extract and persist as JSON."""
        bf = self.extract_function(binary_path, func_name, opt, operator, seed)
        if bf is None:
            return None
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{func_name}.json"
        with json_path.open("w") as f:
            json.dump(bf.to_dict(), f, indent=2)
        return bf
