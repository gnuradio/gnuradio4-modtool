"""Tests for cp command."""

import pytest

from gr4_modtool.commands.cp import copy_block
from gr4_modtool.commands.newblock import write_block_files
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


def test_cp_creates_new_header(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    copy_block(project, "basic", "MyFilter", "MyFilter2")
    assert (project.group_include_dir("basic") / "MyFilter2.hpp").exists()
    assert (project.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_cp_src_header_unchanged(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    original = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    copy_block(project, "basic", "MyFilter", "MyFilter2")
    assert (project.group_include_dir("basic") / "MyFilter.hpp").read_text() == original


def test_cp_substitutes_name_in_header(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    copy_block(project, "basic", "MyFilter", "MyFilter2")
    text = (project.group_include_dir("basic") / "MyFilter2.hpp").read_text()
    assert "struct MyFilter2" in text
    assert "struct MyFilter " not in text  # whole-word — "MyFilter2" can still appear as a new name


def test_cp_to_different_group(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    copy_block(cfg, "basic", "MyFilter", "MyFilter", dst_group="filter")
    assert (cfg.group_include_dir("filter") / "MyFilter.hpp").exists()


def test_cp_updates_namespace_cross_group(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    copy_block(cfg, "basic", "MyFilter", "MyFilter", dst_group="filter")
    text = (cfg.group_include_dir("filter") / "MyFilter.hpp").read_text()
    assert "::filter" in text


def test_cp_gen_test_creates_test_and_cmake_entry(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    copy_block(project, "basic", "MyFilter", "MyFilter2", gen_test=True)
    assert (project.group_test_dir("basic") / "qa_MyFilter2.cpp").exists()
    cmake_text = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "qa_MyFilter2" in cmake_text


def test_cp_raises_if_src_missing(project: ProjectConfig) -> None:
    with pytest.raises(FileNotFoundError):
        copy_block(project, "basic", "Ghost", "Ghost2")


def test_cp_raises_if_dst_exists(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    # Create dst manually
    (project.group_include_dir("basic") / "MyFilter2.hpp").write_text("#pragma once\n")
    with pytest.raises(FileExistsError):
        copy_block(project, "basic", "MyFilter", "MyFilter2")


def test_cp_no_test_by_default(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    copy_block(project, "basic", "MyFilter", "MyFilter2", gen_test=False)
    assert not (project.group_test_dir("basic") / "qa_MyFilter2.cpp").exists()
