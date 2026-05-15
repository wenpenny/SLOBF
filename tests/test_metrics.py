"""Tests for metrics calculation."""

import numpy as np
import pytest

from slobf.metrics.calculator import MetricsCalculator


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 2.0, 3.0])
        assert MetricsCalculator.cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])
        assert MetricsCalculator.cosine_similarity(v1, v2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        v1 = np.array([1.0, 0.0])
        v2 = np.array([-1.0, 0.0])
        assert MetricsCalculator.cosine_similarity(v1, v2) == pytest.approx(-1.0)

    def test_zero_vector(self):
        v1 = np.array([0.0, 0.0])
        v2 = np.array([1.0, 2.0])
        assert MetricsCalculator.cosine_similarity(v1, v2) == 0.0

    def test_similar_vectors(self):
        v1 = np.array([1.0, 2.0, 3.0])
        v2 = np.array([1.1, 2.0, 2.9])
        sim = MetricsCalculator.cosine_similarity(v1, v2)
        assert sim > 0.99


class TestTopKMetrics:
    def test_rank_1(self):
        m = MetricsCalculator.topk_metrics(1)
        assert m["rank"] == 1
        assert m["mrr"] == pytest.approx(1.0)
        assert m["top1_hit"] == 1
        assert m["top5_hit"] == 1
        assert m["top10_hit"] == 1

    def test_rank_3(self):
        m = MetricsCalculator.topk_metrics(3)
        assert m["top1_hit"] == 0
        assert m["top5_hit"] == 1
        assert m["top10_hit"] == 1

    def test_rank_7(self):
        m = MetricsCalculator.topk_metrics(7)
        assert m["top1_hit"] == 0
        assert m["top5_hit"] == 0
        assert m["top10_hit"] == 1
        assert m["mrr"] == pytest.approx(1.0 / 7)

    def test_rank_not_found(self):
        m = MetricsCalculator.topk_metrics(-1)
        assert m["mrr"] == 0.0
        assert m["top1_hit"] == 0


class TestEntropy:
    def test_uniform(self):
        e = MetricsCalculator.calculate_entropy(["a", "b", "c", "d"])
        assert e == pytest.approx(2.0)

    def test_single_value(self):
        e = MetricsCalculator.calculate_entropy(["x", "x", "x", "x"])
        assert e == pytest.approx(0.0)


class TestBinaryDiff:
    def test_growth_ratios(self):
        orig = {"instruction_count": 10, "size": 100, "bb_count": 3, "opcodes": ["mov", "add", "ret"]}
        obs = {"instruction_count": 20, "size": 200, "bb_count": 5, "opcodes": ["mov", "xor", "add", "jmp", "ret"]}
        diff = MetricsCalculator.binary_diff_stats(orig, obs)
        assert diff["instr_growth_ratio"] == 2.0
        assert diff["size_growth_ratio"] == 2.0
        assert diff["bb_count_orig"] == 3
        assert diff["bb_count_obs"] == 5

    def test_zero_division(self):
        orig = {"instruction_count": 0, "size": 0, "bb_count": 0, "opcodes": []}
        obs = {"instruction_count": 5, "size": 10, "bb_count": 1, "opcodes": ["ret"]}
        diff = MetricsCalculator.binary_diff_stats(orig, obs)
        assert diff["instr_growth_ratio"] == 5.0
