"""Tests for the CI build matrix workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.ci import write_ci_matrix
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


def test_ci_matrix_created(cfg: ProjectConfig) -> None:
    written = write_ci_matrix(cfg)
    assert len(written) == 1
    assert written[0].name == "matrix.yml"
    assert written[0].exists()


def test_ci_matrix_has_gcc(cfg: ProjectConfig) -> None:
    write_ci_matrix(cfg)
    text = (cfg.root / ".github" / "workflows" / "matrix.yml").read_text()
    assert "gcc" in text


def test_ci_matrix_has_clang(cfg: ProjectConfig) -> None:
    write_ci_matrix(cfg)
    text = (cfg.root / ".github" / "workflows" / "matrix.yml").read_text()
    assert "clang" in text


def test_ci_matrix_has_build_types(cfg: ProjectConfig) -> None:
    write_ci_matrix(cfg)
    text = (cfg.root / ".github" / "workflows" / "matrix.yml").read_text()
    assert "Debug" in text
    assert "Release" in text
