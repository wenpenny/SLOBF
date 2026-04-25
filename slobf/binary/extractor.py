"""Binary function extraction for SLOBF."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    
    def compute_hashes(self) -> dict[str, str]:
        return {
            "instruction_hash": hashlib.sha256("\n".join(self.disassembly).encode()).hexdigest(),
            "opcode_hash": hashlib.sha256(" ".join(self.opcodes).encode()).hexdigest(),
            "byte_hash": hashlib.sha256(self.bytes_hex.encode()).hexdigest(),
        }

class BinaryExtractor:
    def __init__(self, arch=CS_ARCH_X86, mode=CS_MODE_64):
        self.md = Cs(arch, mode)

    def extract_function(self, binary_path: Path, func_name: str) -> BinaryFunction | None:
        """Extract a function from an ELF binary."""
        if not binary_path.exists():
            return None

        with binary_path.open("rb") as f:
            elffile = ELFFile(f)
            symtab = elffile.get_section_by_name(".symtab")
            if not symtab:
                logger.warning("No symbol table found in %s", binary_path)
                return None

            symbol = None
            for s in symtab.iter_symbols():
                if s.name == func_name:
                    symbol = s
                    break

            if not symbol:
                logger.warning("Symbol %s not found in %s", func_name, binary_path)
                return None

            addr = symbol["st_value"]
            size = symbol["st_size"]
            
            # Find the section containing the symbol
            section = None
            for s in elffile.iter_sections():
                if s["sh_addr"] <= addr < s["sh_addr"] + s["sh_size"]:
                    section = s
                    break
            
            if not section:
                logger.warning("Section for address 0x%x not found", addr)
                return None

            # Get the raw bytes
            offset = addr - section["sh_addr"]
            raw_bytes = section.data()[offset : offset + size]
            
            # Disassemble
            disasm = []
            opcodes = []
            instr_count = 0
            bb_count = 1 # Rough estimate: start with 1 block
            
            for i in self.md.disasm(raw_bytes, addr):
                disasm.append(f"0x{i.address:x}:\t{i.mnemonic}\t{i.op_str}")
                opcodes.append(i.mnemonic)
                instr_count += 1
                # Rough BB count: count jumps/calls/returns
                if i.mnemonic in ["jmp", "je", "jne", "jg", "jl", "ja", "jb", "call", "ret"]:
                    bb_count += 1

            return BinaryFunction(
                name=func_name,
                address=addr,
                size=size,
                disassembly=disasm,
                opcodes=opcodes,
                bytes_hex=raw_bytes.hex(),
                bb_count=bb_count,
                instruction_count=instr_count
            )

    def process_all(self, compile_results_csv: Path, output_dir: Path, threads: int = 1):
        """Process all successfully compiled binaries and extract functions in parallel."""
        if not compile_results_csv.exists():
            return

        import pandas as pd
        df = pd.read_csv(compile_results_csv)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        from concurrent.futures import ThreadPoolExecutor
        from tqdm import tqdm

        def task(row):
            binary_path = Path(row["binary_path"])
            func_name = row["function_id"] if pd.notna(row["function_id"]) else row["project"]
            func = self.extract_function(binary_path, func_name)
            
            if func:
                # Save as JSON
                # Logic to get relative path build/...
                parts = binary_path.parts
                try:
                    build_idx = parts.index("build")
                    rel_path = Path(*parts[build_idx:])
                except ValueError:
                    rel_path = binary_path.name
                
                json_path = output_dir / rel_path.with_suffix(".json")
                json_path.parent.mkdir(parents=True, exist_ok=True)
                
                func_dict = func.__dict__
                func_dict.update(func.compute_hashes())
                
                with json_path.open("w") as f:
                    json.dump(func_dict, f, indent=2)
                
                return {
                    "function_id": func_name,
                    "opt": row["opt"],
                    "operator": row["operator"],
                    "seed": row["seed"],
                    "json_path": str(json_path),
                    "success": True
                }
            return {
                "function_id": func_name,
                "opt": row["opt"],
                "operator": row["operator"],
                "seed": row["seed"],
                "success": False,
                "reason": "Extraction failed"
            }

        valid_rows = df[df["success"] == True]
        with ThreadPoolExecutor(max_workers=threads) as executor:
            results = list(tqdm(executor.map(task, [row for _, row in valid_rows.iterrows()]), 
                                total=len(valid_rows), desc="Extracting functions"))

        pd.DataFrame(results).to_csv(output_dir.parent / "extraction_results.csv", index=False)
