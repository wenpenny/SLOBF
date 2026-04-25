"""utils — Shared utility functions.

Planned contents:
  - file_hash(path) -> str            SHA-256 of a file
  - run_cmd(cmd, timeout) -> CmdResult
  - find_c_files(root) -> list[Path]
  - set_seed(seed)                    numpy + random + torch
  - human_size(bytes) -> str          "4.2 MB"
  - progress_bar(iterable, desc)      thin wrapper around tqdm/rich
"""
