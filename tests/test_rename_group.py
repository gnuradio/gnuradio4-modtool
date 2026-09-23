"""Tests for rename-group command."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.rename_group import cmd, rename_group
from gr4_modtool.project.discovery import ProjectConfig, load_config


def _add_block(project: ProjectConfig, group: str, name: str = "MyFilter") -> None:
    write_block_files(
        project,
        {
            "group_name": group,
            "block_name": name,
            "description": "test block",
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": "float, double",
            "gen_test": True,
        },
    )


# ---------------------------------------------------------------------------
# rename_group() unit tests
# ---------------------------------------------------------------------------


def test_rename_group_moves_directory(project: ProjectConfig) -> None:
    rename_group(project, "basic", "dsp")
    assert not (project.root / "blocks" / "basic").exists()
    assert (project.root / "blocks" / "dsp").exists()


def test_rename_group_renames_include_subdir(project: ProjectConfig) -> None:
    _add_block(project, "basic")
    rename_group(project, "basic", "dsp")
    old_inc = project.root / "blocks" / "dsp" / "include" / "gnuradio-4.0" / "basic"
    new_inc = project.root / "blocks" / "dsp" / "include" / "gnuradio-4.0" / "dsp"
    assert not old_inc.exists()
    assert new_inc.exists()


def test_rename_group_updates_header_namespace(project: ProjectConfig) -> None:
    _add_block(project, "basic")
    rename_group(project, "basic", "dsp")
    hpp = project.root / "blocks" / "dsp" / "include" / "gnuradio-4.0" / "dsp" / "MyFilter.hpp"
    text = hpp.read_text()
    assert "::dsp" in text
    assert "::basic" not in text


def test_rename_group_updates_include_path_in_header(project: ProjectConfig) -> None:
    _add_block(project, "basic")
    rename_group(project, "basic", "dsp")
    hpp = project.root / "blocks" / "dsp" / "include" / "gnuradio-4.0" / "dsp" / "MyFilter.hpp"
    text = hpp.read_text()
    assert "/basic/" not in text


def test_rename_group_updates_include_path_in_test(project: ProjectConfig) -> None:
    _add_block(project, "basic")
    rename_group(project, "basic", "dsp")
    qa = project.root / "blocks" / "dsp" / "test" / "qa_MyFilter.cpp"
    if qa.exists():
        text = qa.read_text()
        assert "/basic/" not in text


def test_rename_group_updates_toml(project: ProjectConfig) -> None:
    rename_group(project, "basic", "dsp")
    cfg = load_config(project.root)
    assert "dsp" in cfg.groups
    assert "basic" not in cfg.groups
    assert cfg.groups["dsp"] == "blocks/dsp"


def test_rename_group_updates_blocks_cmake(project: ProjectConfig) -> None:
    from gr4_modtool.project import cmake as cmake_mod

    blocks_cmake = project.root / "blocks" / "CMakeLists.txt"
    cmake_mod.add_group_to_blocks_cmake(blocks_cmake, "basic", project.cmake_prefix)
    rename_group(project, "basic", "dsp")
    text = blocks_cmake.read_text()
    assert "add_subdirectory(dsp)" in text
    assert "add_subdirectory(basic)" not in text


def test_rename_group_updates_group_cmake_targets(project: ProjectConfig) -> None:
    _add_block(project, "basic")
    rename_group(project, "basic", "dsp")
    text = (project.root / "blocks" / "dsp" / "CMakeLists.txt").read_text()
    assert "blocks_dsp_headers" in text
    assert "blocks_basic_headers" not in text


def test_rename_group_raises_if_old_not_found(project: ProjectConfig) -> None:
    with pytest.raises(ValueError, match="not found"):
        rename_group(project, "nonexistent", "dsp")


def test_rename_group_raises_if_new_exists(project_two_groups: ProjectConfig) -> None:
    with pytest.raises(ValueError, match="already exists"):
        rename_group(project_two_groups, "basic", "filter")


def test_rename_group_raises_on_invalid_name(project: ProjectConfig) -> None:
    with pytest.raises(ValueError, match="snake_case"):
        rename_group(project, "basic", "MyGroup")


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_rename_group_cli(project: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "basic",
            "dsp",
            "--project-dir",
            str(project.root),
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    cfg = load_config(project.root)
    assert "dsp" in cfg.groups
    assert "basic" not in cfg.groups


def test_rename_group_cli_unknown_group(project: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "ghost",
            "dsp",
            "--project-dir",
            str(project.root),
            "--yes",
        ],
    )
    assert result.exit_code != 0
