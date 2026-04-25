"""Tigress obfuscator adapter for SLOBF."""

import subprocess
import os
import logging
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from slobf.obfuscators.base import ObfuscationResult

logger = logging.getLogger(__name__)

class TigressAdapter:
    """Adapter for the Tigress C obfuscator."""
    
    def __init__(self, tigress_path: Optional[str] = None):
        self.tigress_path = tigress_path or os.environ.get("TIGRESS_HOME")
        self.executable = "tigress"
        
    def check_installation(self) -> bool:
        """Check if Tigress is installed and accessible."""
        try:
            res = subprocess.run([self.executable, "--version"], capture_output=True, text=True)
            return res.returncode == 0
        except FileNotFoundError:
            logger.warning("Tigress executable not found. Please ensure 'tigress' is in PATH or TIGRESS_HOME is set.")
            return False

    def obfuscate(self, 
                  source_file: Path, 
                  output_file: Path, 
                  function_name: str, 
                  transformation: str,
                  seed: int = 0) -> ObfuscationResult:
        """Run Tigress transformation on a specific function."""
        
        # Tigress transformations mapping
        # Flatten, Split, EncodeLiterals, AddOpaque
        trans_map = {
            "Flatten": f"--Transform=Virtualize --Functions={function_name}",
            "Split": f"--Transform=Split --Functions={function_name}",
            "EncodeLiterals": f"--Transform=EncodeLiterals --Functions={function_name}",
            "AddOpaque": f"--Transform=InitOpaque --Transform=AddOpaque --Functions={function_name}",
        }
        
        cmd_part = trans_map.get(transformation, f"--Transform={transformation} --Functions={function_name}")
        
        cmd = [
            self.executable,
            f"--Seed={seed}",
            "--Environment=x86_64:Linux:Gcc:4.6", # Default environment
        ]
        
        # Add transformation commands
        cmd.extend(cmd_part.split())
        
        # Input and Output
        cmd.extend(["--Outfile=" + str(output_file), str(source_file)])
        
        logger.debug("Running Tigress: %s", " ".join(cmd))
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                return ObfuscationResult(
                    success=True,
                    changed_source=output_file.read_text() if output_file.exists() else "",
                    operator=f"Tigress_{transformation}",
                    seed=seed
                )
            else:
                logger.error("Tigress failed: %s", res.stderr)
                return ObfuscationResult(success=False, failure_reason=res.stderr)
        except Exception as e:
            logger.error("Tigress execution error: %s", str(e))
            return ObfuscationResult(success=False, failure_reason=str(e))

def get_tigress_install_script():
    """Returns a simple shell script to help users install Tigress if missing."""
    return """
#!/bin/bash
# Tigress installation helper for WSL/Linux
# Note: Tigress requires OCaml and a specific environment.
# Visit http://tigress.cs.arizona.edu/ for official downloads.

echo "Attempting to check Tigress prerequisites..."
sudo apt-get update
sudo apt-get install -y build-essential gcc-multilib

echo "Manual steps required:"
echo "1. Download Tigress from http://tigress.cs.arizona.edu/download.html"
echo "2. Extract it to a directory (e.g., ~/tigress)"
echo "3. Add the following to your .bashrc:"
echo "   export TIGRESS_HOME=~/tigress/x86_64/linux/3.1"
echo "   export PATH=\\$PATH:\\$TIGRESS_HOME"
"""
