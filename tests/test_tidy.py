"""Tests for the tidy command and clang config generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gr4_modtool.commands.tidy import run_tidy, write_ci_clang, write_clang_config
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
        groups={"basic": "blocks/basic"},
    )
    save_config(c)
    return c


# ---------------------------------------------------------------------------
# write_clang_config
# ---------------------------------------------------------------------------


def test_write_clang_config_creates_both_files(cfg: ProjectConfig) -> None:
    written = write_clang_config(cfg)
    names = {p.name for p in written}
    assert ".clang-format" in names
    assert ".clang-tidy" in names


def test_clang_format_has_indent_width(cfg: ProjectConfig) -> None:
    write_clang_config(cfg)
    text = (cfg.root / ".clang-format").read_text()
    assert "IndentWidth" in text


def test_clang_format_has_column_limit(cfg: ProjectConfig) -> None:
    write_clang_config(cfg)
    text = (cfg.root / ".clang-format").read_text()
    assert "ColumnLimit" in text


def test_clang_tidy_has_header_filter(cfg: ProjectConfig) -> None:
    write_clang_config(cfg)
    text = (cfg.root / ".clang-tidy").read_text()
    assert "gnuradio-4.0" in text
    assert "HeaderFilterRegex" in text


def test_clang_tidy_suppresses_public_member_check(cfg: ProjectConfig) -> None:
    write_clang_config(cfg)
    text = (cfg.root / ".clang-tidy").read_text()
    assert "non-private-member-variables-in-classes" in text


def test_write_clang_config_idempotent(cfg: ProjectConfig) -> None:
    write_clang_config(cfg)
    write_clang_config(cfg)
    assert (cfg.root / ".clang-tidy").exists()


# ---------------------------------------------------------------------------
# write_ci_clang
# ---------------------------------------------------------------------------


def test_write_ci_clang_creates_workflow(cfg: ProjectConfig) -> None:
    written = write_ci_clang(cfg)
    assert len(written) == 1
    assert written[0].exists()


def test_ci_workflow_has_clang_tidy_job(cfg: ProjectConfig) -> None:
    write_ci_clang(cfg)
    path = cfg.root / ".github" / "workflows" / "clang-ci.yml"
    text = path.read_text()
    assert "clang-tidy" in text


def test_ci_workflow_has_clang_format_job(cfg: ProjectConfig) -> None:
    write_ci_clang(cfg)
    text = (cfg.root / ".github" / "workflows" / "clang-ci.yml").read_text()
    assert "clang-format" in text


def test_ci_workflow_mentions_compile_commands(cfg: ProjectConfig) -> None:
    write_ci_clang(cfg)
    text = (cfg.root / ".github" / "workflows" / "clang-ci.yml").read_text()
    assert "EXPORT_COMPILE_COMMANDS" in text


# ---------------------------------------------------------------------------
# run_tidy
# ---------------------------------------------------------------------------


def test_run_tidy_graceful_if_not_installed(cfg: ProjectConfig, tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "compile_commands.json").write_text("[]")
    with patch("shutil.which", return_value=None):
        rc = run_tidy(cfg, build_dir)
    assert rc == 0


def test_run_tidy_returns_1_if_no_compile_commands(cfg: ProjectConfig, tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    with patch("shutil.which", return_value="/usr/bin/clang-tidy"):
        rc = run_tidy(cfg, build_dir)
    assert rc == 1


def test_run_tidy_calls_clang_tidy(cfg: ProjectConfig, tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "compile_commands.json").write_text("[]")

    # Create a fake header for the basic group
    inc_dir = cfg.group_include_dir("basic")
    inc_dir.mkdir(parents=True, exist_ok=True)
    (inc_dir / "MyFilter.hpp").write_text("// stub")

    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0

    with (
        patch("shutil.which", return_value="/usr/bin/clang-tidy"),
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        rc = run_tidy(cfg, build_dir)

    assert rc == 0
    args = mock_popen.call_args[0][0]
    assert args[0] == "clang-tidy"
    assert "-p" in args
    assert str(build_dir) in args
    assert any("MyFilter.hpp" in a for a in args)


def test_run_tidy_fix_flag_passed(cfg: ProjectConfig, tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "compile_commands.json").write_text("[]")

    inc_dir = cfg.group_include_dir("basic")
    inc_dir.mkdir(parents=True, exist_ok=True)
    (inc_dir / "MyFilter.hpp").write_text("// stub")

    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0

    with (
        patch("shutil.which", return_value="/usr/bin/clang-tidy"),
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        run_tidy(cfg, build_dir, fix=True)

    args = mock_popen.call_args[0][0]
    assert "--fix" in args
