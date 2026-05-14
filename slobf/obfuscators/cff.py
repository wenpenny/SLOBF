"""Control Flow Flattening (CFF) — AST-based.

Standard algorithm:
1. Recursively decompose the function body into linear basic blocks.
   Each if/for/while is replaced by a conditional dispatch ("cond_goto");
   its body statements are inlined as separate blocks.
2. Assign shuffled numeric IDs to each block.
3. Wrap everything in while(1)/switch(dispatcher).
4. Empty placeholder blocks are pruned; all indices are remapped.
"""

from __future__ import annotations

import random
from slobf.obfuscators.base import BaseObfuscator, ObfuscationResult
from slobf.parser.c_parser import FunctionInfo, CParser
from tree_sitter import Node


class CFFObfuscator(BaseObfuscator):
    name = "CFF"

    _STMT_TYPES = {
        "expression_statement", "declaration", "return_statement",
        "if_statement", "for_statement", "while_statement", "do_statement",
        "break_statement", "continue_statement", "labeled_statement",
    }

    def is_eligible(self, func_info: FunctionInfo) -> tuple[bool, str]:
        ok, reason = super().is_eligible(func_info)
        if not ok:
            return ok, reason
        if func_info.num_statements < 5:
            return False, "Too few statements (< 5)"
        if func_info.has_goto:
            return False, "Contains goto"
        if func_info.has_switch:
            return False, "Already contains switch"
        return True, ""

    def transform(self, source: bytes, func_node: Node, func_info: FunctionInfo,
                  seed: int, intensity: float) -> ObfuscationResult:
        rng = random.Random(seed)
        res = ObfuscationResult(
            success=False, changed=False, operator_name=self.name,
            function_id=func_info.name, seed=seed, intensity=intensity
        )

        parser = CParser()
        body = parser.get_function_body(func_node)
        if not body:
            res.reason_if_failed = "No function body found"
            return res

        # ------------------------------------------------------------------
        # 1. Decompose body into flat blocks
        # ------------------------------------------------------------------
        stmts = [c for c in body.children if c.type in self._STMT_TYPES]
        flat_blocks = self._flatten(stmts, source)

        if len(flat_blocks) < 2:
            res.reason_if_failed = "Only one block after flattening"
            return res

        # ------------------------------------------------------------------
        # 2. Prune empty blocks and remap indices
        #    Empty blocks were "join points" — redirect to the next non-empty
        #    block after them.
        # ------------------------------------------------------------------
        # Build a forward map: each old index -> its replacement
        old_to_new = {}
        next_nonempty = -1
        for i in range(len(flat_blocks) - 1, -1, -1):
            if flat_blocks[i]:
                next_nonempty = i
            old_to_new[i] = next_nonempty if next_nonempty >= 0 else -1

        # Now build the "compressed" index map (only non-empty blocks)
        nonempty_indices = [i for i, b in enumerate(flat_blocks) if b]
        compressed = {old: new for new, old in enumerate(nonempty_indices)}

        def _remap(old_idx: int) -> int:
            """Map an old block index to its new compressed index."""
            resolved = old_to_new.get(old_idx, -1)
            if resolved < 0:
                return -1
            return compressed.get(resolved, -1)

        pruned = []
        for i, block in enumerate(flat_blocks):
            if not block:
                continue
            new_block = []
            for entry in block:
                kind = entry[0]
                if kind == "cond_goto":
                    t_new = _remap(entry[2])
                    f_new = _remap(entry[3])
                    new_block.append(("cond_goto", entry[1], t_new, f_new))
                elif kind == "goto":
                    new_block.append(("goto", _remap(entry[1])))
                else:
                    new_block.append(entry)
            pruned.append(new_block)

        flat_blocks = pruned
        num = len(flat_blocks)

        # ------------------------------------------------------------------
        # 3. Ensure every non-terminal block has a state transition
        # ------------------------------------------------------------------
        for i, block in enumerate(flat_blocks):
            if not block:
                continue
            last = block[-1]
            if last[0] not in ("cond_goto", "goto", "exit"):
                # Add fall-through to next block
                next_idx = i + 1 if i + 1 < num else -1
                block.append(("goto", next_idx))

        # ------------------------------------------------------------------
        # 4. Shuffle IDs and emit dispatcher
        # ------------------------------------------------------------------
        id_map = list(range(num))
        if intensity > 0.3:
            rng.shuffle(id_map)

        state_var = f"slobf_state_{rng.randint(10000, 99999)}"
        body_indent = body.start_point[1]
        inner = body_indent + 4
        case_i = inner + 8
        stmt_i = case_i + 4

        lines = []
        lines.append(f"{' ' * inner}int {state_var} = {id_map[0]};")
        lines.append(f"{' ' * inner}while ({state_var} >= 0) {{")
        lines.append(f"{' ' * case_i}switch ({state_var}) {{")

        for orig_idx, block in enumerate(flat_blocks):
            bid = id_map[orig_idx]
            lines.append(f"{' ' * case_i}case {bid}: {{")
            for kind, *args in block:
                if kind == "stmt":
                    lines.append(f"{' ' * stmt_i}{args[0]}")
                elif kind == "cond_goto":
                    cond, t_bid, f_bid = args
                    t = id_map[t_bid] if t_bid >= 0 else -1
                    f = id_map[f_bid] if f_bid >= 0 else -1
                    lines.append(f"{' ' * stmt_i}{state_var} = ({cond}) ? {t} : {f};")
                elif kind == "goto":
                    target = args[0]
                    t = id_map[target] if target >= 0 else -1
                    lines.append(f"{' ' * stmt_i}{state_var} = {t};")
                elif kind == "exit":
                    lines.append(f"{' ' * stmt_i}{state_var} = -1;")
            lines.append(f"{' ' * case_i}}} break;")

        lines.append(f"{' ' * case_i}default:")
        lines.append(f"{' ' * stmt_i}{state_var} = -1;")
        lines.append(f"{' ' * stmt_i}break;")
        lines.append(f"{' ' * case_i}}}")
        lines.append(f"{' ' * inner}}}")

        # ------------------------------------------------------------------
        # 5. Splice into source
        # ------------------------------------------------------------------
        open_brace = next((c for c in body.children if c.type == "{"), None)
        close_brace = None
        for c in body.children:
            if c.type == "}":
                close_brace = c
        if not open_brace or not close_brace:
            res.reason_if_failed = "Cannot locate body braces"
            return res

        new_body_text = "\n".join(lines)
        new_source = (
            source[:open_brace.end_byte] +
            b"\n" + new_body_text.encode() + b"\n" +
            (" " * body_indent).encode() +
            source[close_brace.start_byte:]
        )

        res.changed_source = new_source.decode("utf-8", errors="ignore")
        res.compute_diff(source.decode("utf-8", errors="ignore"))
        res.success = True
        res.metadata["flat_blocks"] = num
        res.metadata["state_var"] = state_var
        return res

    # ==================================================================
    # Recursive flattening
    # ==================================================================

    def _flatten(self, stmts: list[Node], source: bytes) -> list[list[tuple]]:
        """Recursively flatten a list of statements into basic-block tuples.

        Each returned block is a list of entries:
          ("stmt", text)              — plain statement
          ("cond_goto", cond, t, f)   — conditional branch to block t or f
          ("goto", target)            — unconditional jump to target
          ("exit",)                   — terminal (return/break/continue)
        """
        blocks: list[list[tuple]] = []
        current: list[tuple] = []

        def _flush():
            if current:
                blocks.append(list(current))
                current.clear()

        for stmt in stmts:
            if stmt.type == "if_statement":
                _flush()
                # Parse structure
                cond_node = self._find_condition(stmt, source)
                cond_text = source[cond_node.start_byte:cond_node.end_byte].decode() if cond_node else "1"

                consequence = None
                alternative = None
                for child in stmt.children:
                    if child.type == "else_clause":
                        for ec in child.children:
                            if ec.type in ("compound_statement", "if_statement"):
                                alternative = ec
                    elif child.type in ("compound_statement", "if_statement"):
                        if consequence is None:
                            consequence = child

                # Where blocks will go
                header_idx = len(blocks)  # cond_goto block (filled in later)
                blocks.append([])  # placeholder

                # Then branch
                then_start = len(blocks)
                if consequence and consequence.type == "compound_statement":
                    cons_stmts = [c for c in consequence.children if c.type in self._STMT_TYPES]
                    blocks.extend(self._flatten(cons_stmts, source))
                elif consequence:
                    blocks.extend(self._flatten([consequence], source))
                then_end = len(blocks)

                # Else branch
                else_start = len(blocks)
                if alternative and alternative.type == "compound_statement":
                    alt_stmts = [c for c in alternative.children if c.type in self._STMT_TYPES]
                    blocks.extend(self._flatten(alt_stmts, source))
                elif alternative:
                    blocks.extend(self._flatten([alternative], source))
                else_end = len(blocks)

                # After if-else
                after_idx = len(blocks)

                # Handle empty branches
                t_target = then_start if then_end > then_start else after_idx
                f_target = else_start if else_end > else_start else after_idx

                blocks[header_idx] = [("cond_goto", cond_text, t_target, f_target)]

                # Jump from then branch end to after if-else
                if then_end > then_start:
                    last_then = blocks[then_end - 1]
                    if last_then and last_then[-1][0] not in ("exit", "cond_goto", "goto"):
                        last_then.append(("goto", after_idx))

                # Jump from else branch end to after if-else
                if else_end > else_start:
                    last_else = blocks[else_end - 1]
                    if last_else and last_else[-1][0] not in ("exit", "cond_goto", "goto"):
                        last_else.append(("goto", after_idx))

                # Start collecting after-if statements
                blocks.append([])
                current = blocks[-1]

            elif stmt.type in ("for_statement", "while_statement"):
                _flush()
                cond_node = self._find_condition(stmt, source)
                cond_text = source[cond_node.start_byte:cond_node.end_byte].decode() if cond_node else "1"

                loop_body = None
                for child in stmt.children:
                    if child.type == "compound_statement":
                        loop_body = child
                        break

                header_idx = len(blocks)
                blocks.append([])  # placeholder

                body_start = len(blocks)
                if loop_body:
                    body_stmts = [c for c in loop_body.children if c.type in self._STMT_TYPES]
                    blocks.extend(self._flatten(body_stmts, source))
                body_end = len(blocks)

                after_idx = len(blocks)

                if body_end > body_start:
                    t_target = body_start
                    f_target = after_idx
                    last_body = blocks[body_end - 1]
                    if last_body and last_body[-1][0] not in ("exit", "cond_goto", "goto"):
                        last_body.append(("goto", header_idx))
                else:
                    t_target = after_idx
                    f_target = after_idx

                blocks[header_idx] = [("cond_goto", cond_text, t_target, f_target)]

                blocks.append([])
                current = blocks[-1]

            elif stmt.type == "return_statement":
                text = source[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="ignore")
                current.append(("stmt", text))
                current.append(("exit",))
                _flush()

            elif stmt.type in ("break_statement", "continue_statement"):
                current.append(("exit",))
                _flush()

            else:
                text = source[stmt.start_byte:stmt.end_byte].decode("utf-8", errors="ignore")
                current.append(("stmt", text))

        _flush()
        # Remove trailing empty blocks
        while blocks and not blocks[-1]:
            blocks.pop()
        return blocks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_condition(node: Node, source: bytes) -> Node | None:
        for child in node.children:
            if child.type == "condition_clause":
                for cc in child.children:
                    if cc.type not in ("(", ")"):
                        return cc
            if child.type == "parenthesized_expression":
                return child
        return None
