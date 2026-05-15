"""Tests for configuration loading and merging."""

import tempfile
from pathlib import Path

import pytest

from slobf.config import (
    ModelConfig,
    ModelsConfig,
    SlobfConfig,
    load_config,
)


class TestConfigDefaults:
    def test_load_without_file_returns_defaults(self):
        cfg = load_config()
        assert cfg.seed == 42
        assert cfg.threads == 4
        assert cfg.compiler.cc == "gcc"
        assert "O0" in cfg.compiler.opt_levels
        assert isinstance(cfg.models, ModelsConfig)

    def test_override_top_level(self):
        cfg = load_config(overrides={"seed": 99, "threads": 8})
        assert cfg.seed == 99
        assert cfg.threads == 8

    def test_override_nested(self):
        cfg = load_config(overrides={"compiler": {"cc": "clang"}})
        assert cfg.compiler.cc == "clang"


class TestModelsConfig:
    def test_default_model_config(self):
        cfg = load_config()
        assert isinstance(cfg.models.cebin, ModelConfig)
        assert cfg.models.cebin.path == ""
        assert cfg.models.cebin.type == ""

    def test_model_config_from_yaml(self, tmp_path):
        yaml_content = """
        models:
          cebin:
            path: /tmp/cebin.pt
            type: gnn
          jtrans:
            path: /tmp/jtrans.pt
            type: transformer
        """
        config_file = tmp_path / "test_models.yaml"
        config_file.write_text(yaml_content)

        cfg = load_config(str(config_file))
        assert cfg.models.cebin.path == "/tmp/cebin.pt"
        assert cfg.models.cebin.type == "gnn"
        assert cfg.models.jtrans.path == "/tmp/jtrans.pt"
        assert cfg.models.jtrans.type == "transformer"
        # untouched models keep defaults
        assert cfg.models.clap.path == ""
