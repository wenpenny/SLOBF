"""metrics — Evaluation metrics computation.

Planned metrics:
  cosine_similarity (CS)   — per-pair embedding cosine distance
  top_k_recall             — recall@K for a query pool
  shannon_entropy          — instruction-level entropy of binary
  code_growth_rate         — (obf_size - orig_size) / orig_size
  binary_size_delta        — absolute byte increase
  compile_success_rate     — fraction of functions that compiled
  test_pass_rate           — fraction of test cases still passing

Public API (to be implemented):
  MetricsComputer.cosine_similarity(emb_a, emb_b) -> float
  MetricsComputer.top_k(query, pool, k) -> float
  MetricsComputer.shannon_entropy(binary_function) -> float
  MetricsComputer.code_growth_rate(orig, obf) -> float
  MetricsComputer.compile_success_rate(results) -> float
  MetricsComputer.summarise(results) -> pd.DataFrame
"""
