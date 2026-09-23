"""Tests for mv command."""

import pytest

from gr4_modtool.commands.mv import move_block
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


def test_mv_moves_header(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    move_block(cfg, "basic", "MyFilter", "filter")
    assert (cfg.group_include_dir("filter") / "MyFilter.hpp").exists()
    assert not (cfg.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_mv_moves_test_source(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    move_block(cfg, "basic", "MyFilter", "filter")
    assert (cfg.group_test_dir("filter") / "qa_MyFilter.cpp").exists()
    assert not (cfg.group_test_dir("basic") / "qa_MyFilter.cpp").exists()


def test_mv_updates_namespace_in_header(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    move_block(cfg, "basic", "MyFilter", "filter")
    text = (cfg.group_include_dir("filter") / "MyFilter.hpp").read_text()
    assert "::filter" in text
    assert "::basic" not in text


def test_mv_updates_include_in_test(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    move_block(cfg, "basic", "MyFilter", "filter")
    text = (cfg.group_test_dir("filter") / "qa_MyFilter.cpp").read_text()
    assert "/filter/" in text
    assert "/basic/" not in text


def test_mv_removes_from_src_cmake(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    move_block(cfg, "basic", "MyFilter", "filter")
    text = (cfg.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "qa_MyFilter" not in text


def test_mv_adds_to_dst_cmake(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    move_block(cfg, "basic", "MyFilter", "filter")
    text = (cfg.group_test_dir("filter") / "CMakeLists.txt").read_text()
    assert "qa_MyFilter" in text


def test_mv_raises_if_src_missing(project_two_groups: ProjectConfig) -> None:
    with pytest.raises(FileNotFoundError):
        move_block(project_two_groups, "basic", "Ghost", "filter")


def test_mv_raises_if_dst_exists(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    # Create header in dst too
    dst = cfg.group_include_dir("filter") / "MyFilter.hpp"
    dst.write_text("#pragma once\n")
    with pytest.raises(FileExistsError):
        move_block(cfg, "basic", "MyFilter", "filter")
