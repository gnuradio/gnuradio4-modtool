"""Tests for --json output on info and check commands."""

import json

from click.testing import CliRunner

from gr4_modtool.cli import cli
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import ProjectConfig


def _basic_answers(block: str = "MyFilter") -> dict:
    return {
        "group_name": "basic",
        "block_name": block,
        "description": "Test.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": True,
    }


def _invoke_json(args: list[str], project: ProjectConfig) -> dict:
    # args[0] is the subcommand; --project-dir must come after it
    runner = CliRunner()
    cmd, *opts = args
    result = runner.invoke(cli, [cmd, "--project-dir", str(project.root)] + opts)
    return json.loads(result.output)


def test_info_json_is_valid_json(project: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["info", "--project-dir", str(project.root), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, dict)


def test_info_json_has_project_name(project: ProjectConfig) -> None:
    data = _invoke_json(["info", "--json"], project)
    assert data["name"] == "testmod"


def test_info_json_has_groups_and_blocks(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    data = _invoke_json(["info", "--json"], project)
    group_names = [g["name"] for g in data["groups"]]
    assert "basic" in group_names
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    block_names = [b["name"] for b in basic["blocks"]]
    assert "MyFilter" in block_names


def test_check_json_clean_project(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    data = _invoke_json(["check", "--json"], project)
    assert data["issues"] == []
    assert data["error_count"] == 0


def test_check_json_reports_issue(project: ProjectConfig) -> None:
    # Orphan header with no GR_REGISTER_BLOCK triggers a warning
    (project.group_include_dir("basic") / "Orphan.hpp").write_text(
        "#pragma once\nstruct Orphan {};\n"
    )
    data = _invoke_json(["check", "--json"], project)
    blocks = [i["block"] for i in data["issues"]]
    assert "Orphan" in blocks


def test_check_json_exit_zero_on_warnings(project: ProjectConfig) -> None:
    (project.group_include_dir("basic") / "Orphan.hpp").write_text(
        "#pragma once\nstruct Orphan {};\n"
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--project-dir", str(project.root), "--json"])
    data = json.loads(result.output)
    assert data["error_count"] == 0
    assert result.exit_code == 0


def test_check_json_exit_one_on_errors(project: ProjectConfig) -> None:
    # cmake entry with no matching test source → error
    cmake_test = project.group_test_dir("basic") / "CMakeLists.txt"
    cmake_mod.append_test_entry(
        cmake_test, "Ghost", f"{project.cmake_prefix}::blocks_basic_headers"
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--project-dir", str(project.root), "--json"])
    data = json.loads(result.output)
    assert data["error_count"] > 0
    assert result.exit_code == 1
