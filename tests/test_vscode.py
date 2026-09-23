"""Tests for VS Code settings scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gr4_modtool.commands.vscode import write_vscode
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


def test_vscode_creates_both_files(cfg: ProjectConfig) -> None:
    written = write_vscode(cfg)
    names = {p.name for p in written}
    assert "settings.json" in names
    assert "launch.json" in names
    for p in written:
        assert p.exists()


def test_settings_has_cmake_build_dir(cfg: ProjectConfig) -> None:
    write_vscode(cfg)
    text = (cfg.root / ".vscode" / "settings.json").read_text()
    assert "cmake.buildDirectory" in text


def test_settings_has_clangd_config(cfg: ProjectConfig) -> None:
    write_vscode(cfg)
    text = (cfg.root / ".vscode" / "settings.json").read_text()
    assert "clangd" in text


def test_launch_has_debug_config(cfg: ProjectConfig) -> None:
    write_vscode(cfg)
    data = json.loads((cfg.root / ".vscode" / "launch.json").read_text())
    assert len(data["configurations"]) > 0


def test_vscode_idempotent(cfg: ProjectConfig) -> None:
    write_vscode(cfg)
    write_vscode(cfg)
    data = json.loads((cfg.root / ".vscode" / "settings.json").read_text())
    assert "cmake.buildDirectory" in data
