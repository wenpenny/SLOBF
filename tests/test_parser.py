"""Tests for the C parser."""

from slobf.parser.c_parser import CParser, FunctionInfo


SIMPLE_C = b"""
int add(int a, int b) {
    int c = a + b;
    return c;
}
"""

MULTI_STMT_C = b"""
int compute(int x, int y) {
    int a = x + y;
    int b = x - y;
    int c = a * b;
    if (c > 0) {
        return c;
    } else {
        return -c;
    }
}
"""

STATIC_FUNC_C = b"""
static void helper(int *p) {
    *p = *p * 2;
}
"""


class TestCParser:
    def setup_method(self):
        self.parser = CParser()

    def test_parse_simple_function(self):
        root = self.parser.parse_bytes(SIMPLE_C)
        assert root is not None
        func_node = self.parser.find_function_node(root, "add", SIMPLE_C)
        assert func_node is not None
        assert func_node.type == "function_definition"

    def test_parse_returns_function_info(self):
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".c", delete=False) as f:
            f.write(SIMPLE_C)
            tmp_path = Path(f.name)

        try:
            funcs = self.parser.parse_file(tmp_path, dataset_name="test", program_name="test_prog")
            assert len(funcs) == 1
            f0 = funcs[0]
            assert f0.name == "add"
            assert f0.dataset == "test"
            assert f0.program == "test_prog"
            assert f0.num_statements >= 1
            assert f0.num_returns == 1
        finally:
            tmp_path.unlink()

    def test_find_function_node_returns_none_for_missing(self):
        root = self.parser.parse_bytes(SIMPLE_C)
        assert self.parser.find_function_node(root, "nonexistent", SIMPLE_C) is None

    def test_parse_multi_statement_function(self):
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".c", delete=False) as f:
            f.write(MULTI_STMT_C)
            tmp_path = Path(f.name)

        try:
            funcs = self.parser.parse_file(tmp_path)
            assert len(funcs) == 1
            f0 = funcs[0]
            assert f0.name == "compute"
            assert f0.num_branches >= 1
            assert f0.num_returns >= 2
        finally:
            tmp_path.unlink()

    def test_static_function_detection(self):
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".c", delete=False) as f:
            f.write(STATIC_FUNC_C)
            tmp_path = Path(f.name)

        try:
            funcs = self.parser.parse_file(tmp_path)
            assert len(funcs) == 1
            assert funcs[0].is_static is True
        finally:
            tmp_path.unlink()

    def test_function_info_has_expected_fields(self):
        info = FunctionInfo(name="test_func", source_file="test.c")
        d = info.to_dict()
        assert d["name"] == "test_func"
        assert "eligibility" in d
        assert "ineligible_reason" in d
