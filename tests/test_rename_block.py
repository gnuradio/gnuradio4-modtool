"""Tests for the rename-block command."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.rename_block import cmd, rename_block
from gr4_modtool.project.discovery import ProjectConfig


def _add_block(project: ProjectConfig, name: str = "MyFilter", gen_test: bool = True) -> None:
    write_block_files(
        project,
        {
            "group_name": "basic",
            "block_name": name,
            "description": "test block",
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": "float, double",
            "gen_test": gen_test,
        },
    )


# ---------------------------------------------------------------------------
# rename_block() unit tests
# ---------------------------------------------------------------------------


def test_rename_block_new_header_exists(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    assert (project.group_include_dir("basic") / "MyNewFilter.hpp").exists()


def test_rename_block_old_header_removed(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    assert not (project.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_rename_block_updates_struct_name(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    text = (project.group_include_dir("basic") / "MyNewFilter.hpp").read_text()
    assert "struct MyNewFilter" in text
    assert "struct MyFilter" not in text


def test_rename_block_updates_register_macro(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    text = (project.group_include_dir("basic") / "MyNewFilter.hpp").read_text()
    assert "MyNewFilter" in text
    assert "MyFilter" not in text


def test_rename_block_updates_reflectable_macro(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    text = (project.group_include_dir("basic") / "MyNewFilter.hpp").read_text()
    assert "GR_MAKE_REFLECTABLE(MyNewFilter" in text


def test_rename_block_renames_test_file(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    assert (project.group_test_dir("basic") / "qa_MyNewFilter.cpp").exists()
    assert not (project.group_test_dir("basic") / "qa_MyFilter.cpp").exists()


def test_rename_block_updates_test_include(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    text = (project.group_test_dir("basic") / "qa_MyNewFilter.cpp").read_text()
    assert "MyNewFilter.hpp" in text
    assert "MyFilter.hpp" not in text


def test_rename_block_updates_test_suite_name(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    text = (project.group_test_dir("basic") / "qa_MyNewFilter.cpp").read_text()
    assert '"MyNewFilter"' in text
    assert '"MyFilter"' not in text


def test_rename_block_updates_cmake(project: ProjectConfig) -> None:
    _add_block(project)
    rename_block(project, "basic", "MyFilter", "MyNewFilter")
    text = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "qa_MyNewFilter" in text
    assert "qa_MyFilter" not in text


def test_rename_block_no_test_file_ok(project: ProjectConfig) -> None:
    """Rename succeeds even when the block has no test file."""
    _add_block(project, gen_test=False)
    written = rename_block(project, "basic", "MyFilter", "MyNewFilter")
    assert any("MyNewFilter.hpp" in str(p) for p in written)


def test_rename_block_raises_if_not_found(project: ProjectConfig) -> None:
    with pytest.raises(ValueError, match="not found"):
        rename_block(project, "basic", "Ghost", "NewGhost")


def test_rename_block_raises_if_new_exists(project: ProjectConfig) -> None:
    _add_block(project, name="MyFilter")
    _add_block(project, name="MyOther")
    with pytest.raises(ValueError, match="already exists"):
        rename_block(project, "basic", "MyFilter", "MyOther")


def test_rename_block_raises_on_invalid_name(project: ProjectConfig) -> None:
    _add_block(project)
    with pytest.raises(ValueError, match="CamelCase"):
        rename_block(project, "basic", "MyFilter", "my_filter")


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_rename_block_cli(project: ProjectConfig) -> None:
    _add_block(project)
    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "MyFilter",
            "MyNewFilter",
            "--group",
            "basic",
            "--project-dir",
            str(project.root),
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (project.group_include_dir("basic") / "MyNewFilter.hpp").exists()


def test_rename_block_cli_auto_detects_group(project: ProjectConfig) -> None:
    _add_block(project)
    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "MyFilter",
            "MyNewFilter",
            "--project-dir",
            str(project.root),
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output


def test_rename_block_cli_unknown_block(project: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "Ghost",
            "NewGhost",
            "--project-dir",
            str(project.root),
            "--yes",
        ],
    )
    assert result.exit_code != 0
