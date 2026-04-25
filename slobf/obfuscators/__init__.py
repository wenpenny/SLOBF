"""obfuscators — Source-level semantic-preserving obfuscation operators.

Planned operators (OPx naming follows paper convention):
  OP1  — Opaque predicate insertion
  OP2  — Dead code insertion
  OP3  — Variable renaming
  OP4  — Control-flow flattening (switch-dispatch)
  OP5  — Instruction substitution (a+b → a-(-b))
  OP6  — Loop transformation (for ↔ while, loop unrolling)
  OP7  — Function outlining / inlining
  OP8  — String literal encryption stub
  OP9  — Constant folding reversal (literals → expressions)
  OP10 — Array / struct reordering

Each operator is a class inheriting from BaseObfuscator with:
  .name: str
  .apply(function_record) -> ObfuscatedFunction
  .is_applicable(function_record) -> bool

Public API (to be implemented):
  BaseObfuscator (ABC)
  ObfuscatorRegistry.get(name) -> BaseObfuscator
  apply_pipeline(operators, function_record) -> ObfuscatedFunction
"""
