"""models — Adapters for learning-based binary similarity models.

Supported models (adapters to be implemented):
  cebin     — CEBin (contrastive embedding)
  jtrans    — jTrans (jump-aware transformer)
  clap      — CLAP (cross-lingual assembly pre-training)
  palmtree  — PalmTree (assembly language model)
  trex      — Trex (execution semantics)
  safe      — SAFE (self-attentive function embedding)

Each adapter inherits from BaseModelAdapter with:
  .name: str
  .encode(binary_function) -> np.ndarray
  .similarity(emb_a, emb_b) -> float

Public API (to be implemented):
  BaseModelAdapter (ABC)
  ModelRegistry.get(name) -> BaseModelAdapter
  ModelRegistry.available() -> list[str]
"""
