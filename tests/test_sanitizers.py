"""Tests for sanitizer presets command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gr4_modtool.commands.sanitizers import write_ci_sanitizers, write_cmake_presets
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


def test_cmake_presets_created(cfg: ProjectConfig) -> None:
    write_cmake_presets(cfg)
    assert (cfg.root / "CMakePresets.json").exists()


def test_cmake_presets_valid_json(cfg: ProjectConfig) -> None:
    write_cmake_presets(cfg)
    text = (cfg.root / "CMakePresets.json").read_text()
    data = json.loads(text)
    assert "configurePresets" in data


def test_cmake_presets_has_asan(cfg: ProjectConfig) -> None:
    write_cmake_presets(cfg)
    data = json.loads((cfg.root / "CMakePresets.json").read_text())
    names = [p["name"] for p in data["configurePresets"]]
    assert "asan" in names


def test_cmake_presets_has_ubsan(cfg: ProjectConfig) -> None:
    write_cmake_presets(cfg)
    data = json.loads((cfg.root / "CMakePresets.json").read_text())
    names = [p["name"] for p in data["configurePresets"]]
    assert "ubsan" in names


def test_ci_sanitizers_created(cfg: ProjectConfig) -> None:
    write_ci_sanitizers(cfg)
    assert (cfg.root / ".github" / "workflows" / "sanitizers.yml").exists()


def test_ci_sanitizers_mentions_preset(cfg: ProjectConfig) -> None:
    write_ci_sanitizers(cfg)
    text = (cfg.root / ".github" / "workflows" / "sanitizers.yml").read_text()
    assert "cmake --preset" in text
