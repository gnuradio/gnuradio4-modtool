"""Tests for CI quality workflows (coverage and release)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.ci import write_ci_coverage, write_ci_release
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


def test_ci_coverage_created(cfg: ProjectConfig) -> None:
    written = write_ci_coverage(cfg)
    assert len(written) == 1
    assert written[0].exists()
    assert written[0].name == "coverage.yml"


def test_ci_coverage_mentions_gcovr(cfg: ProjectConfig) -> None:
    write_ci_coverage(cfg)
    text = (cfg.root / ".github" / "workflows" / "coverage.yml").read_text()
    assert "gcovr" in text


def test_ci_coverage_uploads_artifact(cfg: ProjectConfig) -> None:
    write_ci_coverage(cfg)
    text = (cfg.root / ".github" / "workflows" / "coverage.yml").read_text()
    assert "upload-artifact" in text


def test_ci_release_created(cfg: ProjectConfig) -> None:
    written = write_ci_release(cfg)
    assert len(written) == 1
    assert written[0].exists()
    assert written[0].name == "release.yml"


def test_ci_release_triggered_on_tags(cfg: ProjectConfig) -> None:
    write_ci_release(cfg)
    text = (cfg.root / ".github" / "workflows" / "release.yml").read_text()
    assert "tags:" in text
    assert "v*.*.*" in text
