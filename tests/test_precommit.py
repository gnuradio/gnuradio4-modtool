"""Tests for the pre-commit hooks command."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.precommit import write_precommit
from gr4_modtool.project.discovery import ProjectConfig, save_config


@pytest.fixture()
def cfg(tmp_path: Path) -> ProjectConfig:
    c = ProjectConfig(
        root=tmp_path,
        name="mymod",
        version="0.1.0",
        cpp_namespace="gr::mymod",
        cmake_prefix="gr4_mymod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={},
    )
    save_config(c)
    return c


def test_precommit_file_created(cfg: ProjectConfig) -> None:
    written = write_precommit(cfg)
    assert len(written) == 1
    assert written[0].name == ".pre-commit-config.yaml"
    assert written[0].exists()


def test_precommit_has_clang_format_hook(cfg: ProjectConfig) -> None:
    write_precommit(cfg)
    text = (cfg.root / ".pre-commit-config.yaml").read_text()
    assert "clang-format" in text


def test_precommit_has_tidy_hook(cfg: ProjectConfig) -> None:
    write_precommit(cfg)
    text = (cfg.root / ".pre-commit-config.yaml").read_text()
    assert "gr4_modtool" in text or "tidy" in text


def test_precommit_idempotent(cfg: ProjectConfig) -> None:
    write_precommit(cfg)
    write_precommit(cfg)
    assert (cfg.root / ".pre-commit-config.yaml").exists()
