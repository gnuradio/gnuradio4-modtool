"""Tests for flat-mode projects (no groups)."""

from __future__ import annotations

import json

from click.testing import CliRunner

from gr4_modtool.commands.add_test import write_test_for_block
from gr4_modtool.commands.check import audit_project
from gr4_modtool.commands.cp import copy_block
from gr4_modtool.commands.info import cmd as info_cmd
from gr4_modtool.commands.mv import cmd as mv_cmd
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.newgroup import cmd as newgroup_cmd
from gr4_modtool.commands.rename import cmd as rename_cmd
from gr4_modtool.commands.rm import cmd as rm_cmd
from gr4_modtool.commands.show import show_block
from gr4_modtool.commands.status import gather_status
from gr4_modtool.commands.sync import apply_sync, plan_sync
from gr4_modtool.project.discovery import (
    ProjectConfig,
    discover_groups,
    load_config,
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


def test_flat_config_round_trips(project_flat: ProjectConfig) -> None:
    cfg2 = load_config(project_flat.root)
    assert cfg2.flat is True


def test_flat_block_path_methods(project_flat: ProjectConfig) -> None:
    expected_inc = project_flat.root / "blocks" / "include" / "gnuradio-4.0"
    expected_test = project_flat.root / "blocks" / "test"
    assert project_flat.block_include_dir() == expected_inc
    assert project_flat.block_test_dir() == expected_test


def test_group_include_dir_empty_string(project_flat: ProjectConfig) -> None:
    assert project_flat.group_include_dir("") == project_flat.block_include_dir()


def test_group_test_dir_empty_string(project_flat: ProjectConfig) -> None:
    assert project_flat.group_test_dir("") == project_flat.block_test_dir()


def test_discover_groups_flat_returns_synthetic_entry(project_flat: ProjectConfig) -> None:
    groups = discover_groups(project_flat)
    assert len(groups) == 1
    assert groups[0].name == ""
    assert groups[0].path == project_flat.blocks_dir


def test_discover_groups_flat_scans_blocks(project_flat: ProjectConfig) -> None:
    (project_flat.block_include_dir() / "Foo.hpp").write_text("// stub\n")
    (project_flat.block_include_dir() / "Bar.hpp").write_text("// stub\n")
    groups = discover_groups(project_flat)
    names = [b.name for b in groups[0].blocks]
    assert names == ["Bar", "Foo"]


# ---------------------------------------------------------------------------
# Block creation
# ---------------------------------------------------------------------------


def _flat_answers(block: str = "Amplifier") -> dict:
    return {
        "group_name": "",
        "block_name": block,
        "description": "Flat test block.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": True,
    }


def test_newblock_flat_header_path(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    header = project_flat.block_include_dir() / "Amplifier.hpp"
    assert header.exists()


def test_newblock_flat_namespace(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    header = project_flat.block_include_dir() / "Amplifier.hpp"
    text = header.read_text()
    assert "gr::testmod" in text
    assert "gr::testmod::basic" not in text


def test_newblock_flat_include_in_test(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    test = project_flat.block_test_dir() / "qa_Amplifier.cpp"
    assert test.exists()
    text = test.read_text()
    assert "#include <gnuradio-4.0/Amplifier.hpp>" in text
    assert "gnuradio-4.0/basic/Amplifier.hpp" not in text


def test_newblock_flat_cmake_target(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    cmake = project_flat.block_test_dir() / "CMakeLists.txt"
    text = cmake.read_text()
    assert "gr4_testmod::blocks_headers" in text


# ---------------------------------------------------------------------------
# add-test
# ---------------------------------------------------------------------------


def _make_flat_header(project_flat: ProjectConfig, name: str = "Mixer") -> None:
    header = project_flat.block_include_dir() / f"{name}.hpp"
    header.write_text(
        f"""\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_MAKE_REFLECTABLE({name});
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod
GR_REGISTER_BLOCK({name}, gr::testmod, {name}, [float, double])
"""
    )


def test_add_test_flat(project_flat: ProjectConfig) -> None:
    _make_flat_header(project_flat)
    written = write_test_for_block(project_flat, "", "Mixer")
    paths = [p.name for p in written]
    assert "qa_Mixer.cpp" in paths
    test_text = (project_flat.block_test_dir() / "qa_Mixer.cpp").read_text()
    assert "#include <gnuradio-4.0/Mixer.hpp>" in test_text


def test_add_test_flat_cmake_target(project_flat: ProjectConfig) -> None:
    _make_flat_header(project_flat)
    write_test_for_block(project_flat, "", "Mixer")
    cmake = project_flat.block_test_dir() / "CMakeLists.txt"
    assert "gr4_testmod::blocks_headers" in cmake.read_text()


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------


def test_rm_flat(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    runner = CliRunner()
    result = runner.invoke(
        rm_cmd,
        ["Amplifier", "--project-dir", str(project_flat.root), "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert not (project_flat.block_include_dir() / "Amplifier.hpp").exists()


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------


def test_rename_flat(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    runner = CliRunner()
    result = runner.invoke(
        rename_cmd,
        ["Amplifier", "Booster", "--project-dir", str(project_flat.root), "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert (project_flat.block_include_dir() / "Booster.hpp").exists()
    assert not (project_flat.block_include_dir() / "Amplifier.hpp").exists()


# ---------------------------------------------------------------------------
# cp
# ---------------------------------------------------------------------------


def test_cp_flat(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    written = copy_block(project_flat, "", "Amplifier", "Booster", gen_test=True)
    names = [p.name for p in written]
    assert "Booster.hpp" in names
    assert "qa_Booster.cpp" in names


def test_cp_flat_cmake_target(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    copy_block(project_flat, "", "Amplifier", "Booster", gen_test=True)
    cmake = project_flat.block_test_dir() / "CMakeLists.txt"
    assert "gr4_testmod::blocks_headers" in cmake.read_text()


# ---------------------------------------------------------------------------
# status / check
# ---------------------------------------------------------------------------


def test_status_flat_indicator(project_flat: ProjectConfig) -> None:
    status = gather_status(project_flat)
    assert status.flat is True
    assert len(status.groups) == 1
    assert status.groups[0].name == ""


def test_check_flat_detects_missing_test(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, {**_flat_answers(), "gen_test": False})
    from gr4_modtool.commands.check import audit_project

    issues = audit_project(project_flat)
    missing = [i for i in issues if i.block == "Amplifier" and "test" in i.issue.lower()]
    assert missing


def test_check_flat_clean(project_flat: ProjectConfig) -> None:
    write_block_files(project_flat, _flat_answers())
    from gr4_modtool.commands.check import audit_project

    issues = audit_project(project_flat)
    missing = [i for i in issues if i.block == "Amplifier" and "test" in i.issue.lower()]
    assert not missing


# ---------------------------------------------------------------------------
# newgroup / mv guard
# ---------------------------------------------------------------------------


def test_newgroup_errors_on_flat(project_flat: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        newgroup_cmd,
        ["--name", "extra", "--project-dir", str(project_flat.root)],
    )
    assert result.exit_code != 0


def test_mv_errors_on_flat(project_flat: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        mv_cmd,
        ["--from", "basic", "--to", "filter", "--project-dir", str(project_flat.root)],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# rm — full removal (test file + build entries)
# ---------------------------------------------------------------------------


def test_rm_flat_removes_test_source(project_flat: ProjectConfig) -> None:
    """rm also deletes the qa_*.cpp test file."""
    write_block_files(project_flat, _flat_answers())
    runner = CliRunner()
    result = runner.invoke(
        rm_cmd,
        ["Amplifier", "--project-dir", str(project_flat.root), "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert not (project_flat.block_test_dir() / "qa_Amplifier.cpp").exists()


def test_rm_flat_removes_cmake_entry(project_flat: ProjectConfig) -> None:
    """rm removes the block's entry from CMakeLists.txt."""
    write_block_files(project_flat, _flat_answers())
    cmake = project_flat.block_test_dir() / "CMakeLists.txt"
    assert "Amplifier" in cmake.read_text()
    runner = CliRunner()
    runner.invoke(rm_cmd, ["Amplifier", "--project-dir", str(project_flat.root), "--yes"])
    assert "Amplifier" not in cmake.read_text()


def test_rm_flat_output_message(project_flat: ProjectConfig) -> None:
    """rm output says "(flat layout)" rather than a group name."""
    write_block_files(project_flat, _flat_answers())
    runner = CliRunner()
    result = runner.invoke(rm_cmd, ["Amplifier", "--project-dir", str(project_flat.root), "--yes"])
    assert "flat layout" in result.output


# ---------------------------------------------------------------------------
# rename — build files and header content updated
# ---------------------------------------------------------------------------


def test_rename_flat_header_content_updated(project_flat: ProjectConfig) -> None:
    """Renamed header contains the new struct name."""
    write_block_files(project_flat, _flat_answers())
    runner = CliRunner()
    runner.invoke(
        rename_cmd,
        ["Amplifier", "Booster", "--project-dir", str(project_flat.root), "--yes"],
    )
    text = (project_flat.block_include_dir() / "Booster.hpp").read_text()
    assert "Booster" in text
    assert "Amplifier" not in text


def test_rename_flat_cmake_entry_updated(project_flat: ProjectConfig) -> None:
    """Renaming a block updates the CMakeLists.txt entry."""
    write_block_files(project_flat, _flat_answers())
    runner = CliRunner()
    runner.invoke(
        rename_cmd,
        ["Amplifier", "Booster", "--project-dir", str(project_flat.root), "--yes"],
    )
    cmake = (project_flat.block_test_dir() / "CMakeLists.txt").read_text()
    assert "Booster" in cmake
    assert "Amplifier" not in cmake


def test_rename_flat_output_message(project_flat: ProjectConfig) -> None:
    """rename output says "(flat layout)" rather than a group name."""
    write_block_files(project_flat, _flat_answers())
    runner = CliRunner()
    result = runner.invoke(
        rename_cmd,
        ["Amplifier", "Booster", "--project-dir", str(project_flat.root), "--yes"],
    )
    assert "flat layout" in result.output


# ---------------------------------------------------------------------------
# check — cmake entry errors in flat mode
# ---------------------------------------------------------------------------


def _make_flat_test_source(project_flat: ProjectConfig, name: str) -> None:
    """Write a minimal qa_<name>.cpp without updating build files."""
    src = project_flat.block_test_dir() / f"qa_{name}.cpp"
    src.write_text(f"#include <gnuradio-4.0/{name}.hpp>\nint main() {{ return 0; }}\n")


def test_check_flat_missing_cmake_entry(project_flat: ProjectConfig) -> None:
    """check reports an error when a test source has no CMake entry."""
    _make_flat_header(project_flat, "Mixer")
    _make_flat_test_source(project_flat, "Mixer")
    issues = audit_project(project_flat)
    cmake_errs = [i for i in issues if i.block == "Mixer" and "CMake" in i.issue]
    assert cmake_errs
    assert cmake_errs[0].severity == "error"


# ---------------------------------------------------------------------------
# sync — plan and apply in flat mode
# ---------------------------------------------------------------------------


def test_sync_plan_flat_generates_test(project_flat: ProjectConfig) -> None:
    """plan_sync produces a generate_test action for a header without a test."""
    _make_flat_header(project_flat, "Mixer")
    actions = plan_sync(project_flat)
    assert any(a.block == "Mixer" and a.action == "generate_test" for a in actions)


def test_sync_plan_flat_add_cmake_entry(project_flat: ProjectConfig) -> None:
    """plan_sync produces an add_cmake_entry action when test source lacks cmake entry."""
    _make_flat_header(project_flat, "Mixer")
    _make_flat_test_source(project_flat, "Mixer")
    actions = plan_sync(project_flat)
    assert any(a.block == "Mixer" and a.action == "add_cmake_entry" for a in actions)


def test_sync_apply_flat_creates_test_stub(project_flat: ProjectConfig) -> None:
    """apply_sync writes a qa_*.cpp test stub with the flat include path."""
    _make_flat_header(project_flat, "Mixer")
    actions = plan_sync(project_flat)
    apply_sync(project_flat, actions)
    test_file = project_flat.block_test_dir() / "qa_Mixer.cpp"
    assert test_file.exists()
    assert "#include <gnuradio-4.0/Mixer.hpp>" in test_file.read_text()


def test_sync_apply_flat_adds_cmake_entry(project_flat: ProjectConfig) -> None:
    """apply_sync wires the generated test into CMakeLists.txt."""
    _make_flat_header(project_flat, "Mixer")
    actions = plan_sync(project_flat)
    apply_sync(project_flat, actions)
    cmake = (project_flat.block_test_dir() / "CMakeLists.txt").read_text()
    assert "Mixer" in cmake


def test_sync_plan_flat_group_is_empty_string(project_flat: ProjectConfig) -> None:
    """SyncAction.group is '' (not None or a group name) in flat mode."""
    _make_flat_header(project_flat, "Mixer")
    actions = plan_sync(project_flat)
    assert all(a.group == "" for a in actions)


# ---------------------------------------------------------------------------
# discover_groups — edge cases
# ---------------------------------------------------------------------------


def test_discover_groups_flat_no_include_dir(project_flat: ProjectConfig) -> None:
    """discover_groups returns one group with no blocks when include dir is absent."""
    import shutil

    shutil.rmtree(project_flat.block_include_dir())
    groups = discover_groups(project_flat)
    assert len(groups) == 1
    assert groups[0].blocks == []


# ---------------------------------------------------------------------------
# info command
# ---------------------------------------------------------------------------


def test_info_flat_json_group_name(project_flat: ProjectConfig) -> None:
    """info --json has groups[0].name == '' in flat mode."""
    (project_flat.block_include_dir() / "Mixer.hpp").write_text("// stub\n")
    runner = CliRunner()
    result = runner.invoke(info_cmd, ["--json", "--project-dir", str(project_flat.root)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["groups"][0]["name"] == ""


def test_info_flat_json_lists_blocks(project_flat: ProjectConfig) -> None:
    """info --json lists the flat blocks under groups[0].blocks."""
    (project_flat.block_include_dir() / "Mixer.hpp").write_text("// stub\n")
    runner = CliRunner()
    result = runner.invoke(info_cmd, ["--json", "--project-dir", str(project_flat.root)])
    data = json.loads(result.output)
    block_names = [b["name"] for b in data["groups"][0]["blocks"]]
    assert "Mixer" in block_names


def test_info_flat_table_no_group_column(project_flat: ProjectConfig) -> None:
    """info table output suppresses the Group column in flat mode."""
    (project_flat.block_include_dir() / "Mixer.hpp").write_text("// stub\n")
    runner = CliRunner()
    result = runner.invoke(info_cmd, ["--project-dir", str(project_flat.root)])
    assert result.exit_code == 0, result.output
    assert "Group" not in result.output


# ---------------------------------------------------------------------------
# show command
# ---------------------------------------------------------------------------


def test_show_flat_header(project_flat: ProjectConfig) -> None:
    """show_block with group='' finds the header at the flat include path."""
    (project_flat.block_include_dir() / "Mixer.hpp").write_text("// flat header\n")
    show_block(project_flat, "", "Mixer")  # must not raise


def test_show_flat_test_file(project_flat: ProjectConfig) -> None:
    """show_block with show_test=True finds qa_*.cpp at the flat test path."""
    (project_flat.block_test_dir() / "qa_Mixer.cpp").write_text("// flat test\n")
    show_block(project_flat, "", "Mixer", show_test=True)  # must not raise


def test_show_flat_missing_file_raises(project_flat: ProjectConfig) -> None:
    """show_block raises FileNotFoundError when the header doesn't exist."""
    import pytest

    with pytest.raises(FileNotFoundError):
        show_block(project_flat, "", "Ghost")
