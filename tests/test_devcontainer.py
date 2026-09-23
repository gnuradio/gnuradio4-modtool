"""Tests for the devcontainer command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gr4_modtool.commands.devcontainer import write_devcontainer
from gr4_modtool.project.discovery import ProjectConfig, save_config


@pytest.fixture()
def cfg(tmp_path: Path) -> ProjectConfig:
    c = ProjectConfig(
        root=tmp_path,
        name="myfilters",
        version="0.1.0",
        cpp_namespace="gr::myfilters",
        cmake_prefix="gr4_myfilters",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={},
    )
    save_config(c)
    return c


def test_creates_both_files(cfg: ProjectConfig) -> None:
    written = write_devcontainer(cfg)
    names = {p.name for p in written}
    assert "devcontainer.json" in names
    assert "Dockerfile" in names


def test_files_exist_on_disk(cfg: ProjectConfig) -> None:
    write_devcontainer(cfg)
    assert (cfg.root / ".devcontainer" / "devcontainer.json").exists()
    assert (cfg.root / ".devcontainer" / "Dockerfile").exists()


def test_devcontainer_json_is_valid(cfg: ProjectConfig) -> None:
    write_devcontainer(cfg)
    text = (cfg.root / ".devcontainer" / "devcontainer.json").read_text()
    data = json.loads(text)  # raises if invalid
    assert isinstance(data, dict)


def test_devcontainer_json_has_project_name(cfg: ProjectConfig) -> None:
    write_devcontainer(cfg)
    data = json.loads((cfg.root / ".devcontainer" / "devcontainer.json").read_text())
    assert data["name"] == "myfilters"


def test_devcontainer_json_has_post_create_command(cfg: ProjectConfig) -> None:
    write_devcontainer(cfg)
    data = json.loads((cfg.root / ".devcontainer" / "devcontainer.json").read_text())
    assert "gr4_modtool" in data.get("postCreateCommand", "")


def test_dockerfile_has_from_line(cfg: ProjectConfig) -> None:
    write_devcontainer(cfg)
    text = (cfg.root / ".devcontainer" / "Dockerfile").read_text()
    assert text.startswith("# Development container")
    assert "FROM mcr.microsoft.com/devcontainers/cpp" in text


def test_dockerfile_mentions_gnuradio4(cfg: ProjectConfig) -> None:
    write_devcontainer(cfg)
    text = (cfg.root / ".devcontainer" / "Dockerfile").read_text()
    assert "gnuradio4" in text


def test_idempotent(cfg: ProjectConfig) -> None:
    write_devcontainer(cfg)
    write_devcontainer(cfg)  # second call must not raise
    assert (cfg.root / ".devcontainer" / "devcontainer.json").exists()
