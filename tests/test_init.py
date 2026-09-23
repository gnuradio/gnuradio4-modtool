"""Tests for init command."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from gr4_modtool.commands.init import cmd, scan_project_dir, write_init_config
from gr4_modtool.project.discovery import CONFIG_FILE, load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GR4_HEADER = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
GR_REGISTER_BLOCK(gr::basic::MyFilter, [float, double])
"""

_UTIL_HEADER = """\
#pragma once
// Utility types — not a block
struct MyHelper {};
"""


def _make_project_skeleton(
    tmp_path: Path, name: str = "myproj", version: str | None = None
) -> Path:
    ver_line = f" VERSION {version}" if version else ""
    (tmp_path / "CMakeLists.txt").write_text(
        f"cmake_minimum_required(VERSION 3.22)\nproject({name} LANGUAGES CXX{ver_line})\n"
    )
    blocks = tmp_path / "blocks"
    blocks.mkdir()
    for group in ("basic", "filter"):
        inc = blocks / group / "include" / "gnuradio-4.0" / group
        inc.mkdir(parents=True)
    return tmp_path


def _add_blocks(project: Path, group: str, names: list[str], content: str = _GR4_HEADER) -> None:
    inc = project / "blocks" / group / "include" / "gnuradio-4.0" / group
    inc.mkdir(parents=True, exist_ok=True)
    for name in names:
        (inc / f"{name}.hpp").write_text(content)


# ---------------------------------------------------------------------------
# Existing tests (preserved)
# ---------------------------------------------------------------------------


def test_scan_detects_name(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("project(mymod LANGUAGES CXX VERSION 0.1)\n")
    result = scan_project_dir(tmp_path)
    assert result["name"] == "mymod"


def test_scan_detects_groups(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    result = scan_project_dir(tmp_path)
    assert "basic" in result["groups"]
    assert "filter" in result["groups"]


def test_scan_detects_include_prefix(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    result = scan_project_dir(tmp_path)
    assert result["gr4_include_prefix"] == "gnuradio-4.0"


def test_scan_detects_cmake(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    result = scan_project_dir(tmp_path)
    assert result["has_cmake"] is True


def test_write_init_config_creates_toml(tmp_path: Path) -> None:
    write_init_config(
        tmp_path,
        "testmod",
        "0.1.0",
        "gr::testmod",
        "gr4_testmod",
        "gnuradio-4.0",
        True,
        {"basic": "blocks/basic"},
    )
    assert (tmp_path / CONFIG_FILE).exists()
    cfg = load_config(tmp_path)
    assert cfg.name == "testmod"
    assert cfg.cmake_prefix == "gr4_testmod"
    assert "basic" in cfg.groups


def test_write_init_config_raises_if_exists(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILE).write_text("[project]\nname = 'x'\n")
    with pytest.raises(FileExistsError):
        write_init_config(tmp_path, "x", "0.1.0", "gr::x", "gr4_x", "gnuradio-4.0", True, {})


def test_scan_no_blocks_dir(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("project(empty LANGUAGES CXX)\n")
    result = scan_project_dir(tmp_path)
    assert result["groups"] == {}


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------


def test_scan_detects_blocks_in_group(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    _add_blocks(tmp_path, "basic", ["AGC", "Copy", "DCBlocker"])
    result = scan_project_dir(tmp_path)
    assert set(result["group_blocks"]["basic"]) == {"AGC", "Copy", "DCBlocker"}


def test_scan_counts_blocks(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    _add_blocks(tmp_path, "basic", ["A", "B", "C", "D"])
    _add_blocks(tmp_path, "filter", ["X", "Y"])
    result = scan_project_dir(tmp_path)
    assert len(result["group_blocks"]["basic"]) == 4
    assert len(result["group_blocks"]["filter"]) == 2


def test_scan_detects_version_from_cmake(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path, name="mymod", version="1.2.3")
    result = scan_project_dir(tmp_path)
    assert result["version"] == "1.2.3"


def test_scan_version_defaults_when_absent(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("project(mymod LANGUAGES CXX)\n")
    result = scan_project_dir(tmp_path)
    assert result["version"] == "0.1.0"


def test_scan_flat_layout(tmp_path: Path) -> None:
    """include/gnuradio-4.0/basic/*.hpp at root (no blocks/ subdir)."""
    inc = tmp_path / "include" / "gnuradio-4.0" / "basic"
    inc.mkdir(parents=True)
    (inc / "MyFilter.hpp").write_text(_GR4_HEADER)
    result = scan_project_dir(tmp_path)
    assert "basic" in result["groups"]
    assert "MyFilter" in result["group_blocks"]["basic"]
    assert result["gr4_include_prefix"] == "gnuradio-4.0"


def test_scan_src_blocks_layout(tmp_path: Path) -> None:
    """src/blocks/<group>/include/ layout (no top-level blocks/)."""
    inc = tmp_path / "src" / "blocks" / "dsp" / "include" / "gnuradio-4.0" / "dsp"
    inc.mkdir(parents=True)
    (inc / "FIR.hpp").write_text(_GR4_HEADER)
    result = scan_project_dir(tmp_path)
    assert "dsp" in result["groups"]
    assert "FIR" in result["group_blocks"]["dsp"]


def test_init_dry_run_no_file_written(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cmd, ["--project-dir", str(tmp_path), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert not (tmp_path / CONFIG_FILE).exists()
    assert "dry-run" in result.output


def test_init_force_overwrites(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    (tmp_path / CONFIG_FILE).write_text("[project]\nname = 'old'\n")
    runner = CliRunner()
    result = runner.invoke(cmd, ["--project-dir", str(tmp_path), "--yes", "--force"])
    assert result.exit_code == 0
    cfg = load_config(tmp_path)
    assert cfg.name == "myproj"


def test_init_force_refused_without_flag(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    (tmp_path / CONFIG_FILE).write_text("[project]\nname = 'old'\n")
    runner = CliRunner()
    result = runner.invoke(cmd, ["--project-dir", str(tmp_path), "--yes"])
    assert result.exit_code != 0


def test_init_yes_uses_detected_version(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path, version="2.0.0")
    runner = CliRunner()
    runner.invoke(cmd, ["--project-dir", str(tmp_path), "--yes"])
    cfg = load_config(tmp_path)
    assert cfg.version == "2.0.0"


def test_init_output_shows_block_count(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    _add_blocks(tmp_path, "basic", ["AGC", "Copy"])
    runner = CliRunner()
    result = runner.invoke(cmd, ["--project-dir", str(tmp_path), "--yes"])
    assert result.exit_code == 0
    assert "2 block" in result.output


def test_write_init_config_force_flag(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILE).write_text("[project]\nname = 'old'\n")
    write_init_config(
        tmp_path,
        "new",
        "1.0.0",
        "gr::new_",
        "gr4_new",
        "gnuradio-4.0",
        True,
        {},
        force=True,
    )
    cfg = load_config(tmp_path)
    assert cfg.name == "new"
