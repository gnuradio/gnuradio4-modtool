"""Tests for check command."""

from gr4_modtool.commands.check import audit_project
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import ProjectConfig


def _basic_answers(block: str = "MyFilter") -> dict:
    return {
        "group_name": "basic",
        "block_name": block,
        "description": "Test block.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": True,
    }


def test_no_issues_on_clean_project(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    issues = audit_project(project)
    assert issues == []


def test_header_missing_register_macro(project: ProjectConfig) -> None:
    header = project.group_include_dir("basic") / "Bare.hpp"
    header.write_text("#pragma once\nstruct Bare {};\n")
    issues = audit_project(project)
    bare_issues = [i for i in issues if i.block == "Bare"]
    assert any("GR_REGISTER_BLOCK" in i.issue for i in bare_issues)
    assert all(i.severity == "warning" for i in bare_issues)


def test_header_with_no_test(project: ProjectConfig) -> None:
    write_block_files(project, {**_basic_answers("NoTest"), "gen_test": False})
    issues = audit_project(project)
    no_test_issues = [i for i in issues if i.block == "NoTest"]
    assert any("no test source" in i.issue for i in no_test_issues)
    assert all(i.severity == "warning" for i in no_test_issues)


def test_test_source_no_cmake_entry(project: ProjectConfig) -> None:
    # Create a test source without adding cmake entry
    (project.group_test_dir("basic") / "qa_Orphan.cpp").write_text("// orphan\n")
    issues = audit_project(project)
    orphan_issues = [i for i in issues if i.block == "Orphan"]
    assert any("no CMake entry" in i.issue for i in orphan_issues)
    assert any(i.severity == "error" for i in orphan_issues)


def test_cmake_entry_no_source(project: ProjectConfig) -> None:
    cmake_test = project.group_test_dir("basic") / "CMakeLists.txt"
    cmake_mod.append_test_entry(
        cmake_test, "Ghost", f"{project.cmake_prefix}::blocks_basic_headers"
    )
    issues = audit_project(project)
    ghost_issues = [i for i in issues if i.block == "Ghost"]
    assert any("CMake entry has no test source" in i.issue for i in ghost_issues)
    assert any(i.severity == "error" for i in ghost_issues)


def test_check_group_filter(project: ProjectConfig) -> None:
    header = project.group_include_dir("basic") / "Bare.hpp"
    header.write_text("#pragma once\nstruct Bare {};\n")
    issues_all = audit_project(project)
    issues_basic = audit_project(project, groups=["basic"])
    assert len(issues_basic) <= len(issues_all)
    assert all(i.group == "basic" for i in issues_basic)


def test_clean_project_no_errors(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    issues = audit_project(project)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []
