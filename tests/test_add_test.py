"""Tests for add-test command and parse_header_info."""

import pytest

from gr4_modtool.commands.add_test import parse_header_info, write_test_for_block
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.project.discovery import ProjectConfig


def _basic_answers(block: str = "MyFilter", processing_style: str = "processOne") -> dict:
    return {
        "group_name": "basic",
        "block_name": block,
        "description": "Test block.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": processing_style,
        "type_list": "float, double",
        "gen_test": False,
    }


def test_write_test_creates_file(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    written = write_test_for_block(project, "basic", "MyFilter")
    assert any("qa_MyFilter.cpp" in str(p) for p in written)
    assert (project.group_test_dir("basic") / "qa_MyFilter.cpp").exists()


def test_write_test_content_has_namespace(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_test_for_block(project, "basic", "MyFilter")
    text = (project.group_test_dir("basic") / "qa_MyFilter.cpp").read_text()
    assert "testmod" in text or "gr::" in text or "MyFilter" in text


def test_write_test_updates_cmake(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_test_for_block(project, "basic", "MyFilter")
    cmake_text = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "qa_MyFilter" in cmake_text


def test_write_test_raises_if_header_missing(project: ProjectConfig) -> None:
    with pytest.raises(FileNotFoundError):
        write_test_for_block(project, "basic", "Ghost")


def test_write_test_raises_if_test_exists(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    # Create the test file to trigger FileExistsError
    (project.group_test_dir("basic") / "qa_MyFilter.cpp").write_text("// exists\n")
    with pytest.raises(FileExistsError):
        write_test_for_block(project, "basic", "MyFilter")


def test_parse_header_template_params(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    header = project.group_include_dir("basic") / "MyFilter.hpp"
    info = parse_header_info(header)
    assert "T" in info["template_params"]


def test_parse_header_in_ports(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    header = project.group_include_dir("basic") / "MyFilter.hpp"
    info = parse_header_info(header)
    assert any(p["name"] == "in" for p in info["in_ports"])


def test_parse_header_out_ports(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    header = project.group_include_dir("basic") / "MyFilter.hpp"
    info = parse_header_info(header)
    assert any(p["name"] == "out" for p in info["out_ports"])


def test_parse_header_type_list(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    header = project.group_include_dir("basic") / "MyFilter.hpp"
    info = parse_header_info(header)
    assert "float" in info["type_list"]


def test_parse_header_processing_style(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers(processing_style="processOne"))
    header = project.group_include_dir("basic") / "MyFilter.hpp"
    info = parse_header_info(header)
    assert info["processing_style"] == "processOne"
