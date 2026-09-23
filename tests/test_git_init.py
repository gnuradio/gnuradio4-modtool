"""Tests for git init option in newmod."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gr4_modtool.commands.newmod import write_git_init
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


def test_gitignore_created(cfg: ProjectConfig) -> None:
    write_git_init(cfg)
    assert (cfg.root / ".gitignore").exists()


def test_gitignore_has_build_entry(cfg: ProjectConfig) -> None:
    write_git_init(cfg)
    text = (cfg.root / ".gitignore").read_text()
    assert "build/" in text


def test_gitignore_has_cmake_cache(cfg: ProjectConfig) -> None:
    write_git_init(cfg)
    text = (cfg.root / ".gitignore").read_text()
    assert "CMakeCache.txt" in text


def test_git_init_called_when_git_available(cfg: ProjectConfig) -> None:
    with patch("shutil.which", return_value="/usr/bin/git"), patch("subprocess.run") as mock_run:
        write_git_init(cfg)
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "git"
    assert "init" in args


def test_git_init_skipped_when_git_missing(cfg: ProjectConfig) -> None:
    with patch("shutil.which", return_value=None), patch("subprocess.run") as mock_run:
        write_git_init(cfg)
    mock_run.assert_not_called()
