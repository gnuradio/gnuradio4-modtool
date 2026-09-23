"""Integration tests for the newblock write path."""

from __future__ import annotations

from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.project.discovery import ProjectConfig


def _basic_answers(group: str = "basic", block: str = "MyFilter") -> dict:
    return {
        "group_name": group,
        "block_name": block,
        "description": "A test filter block.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": True,
    }


def test_newblock_creates_header(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    header = project.group_include_dir("basic") / "MyFilter.hpp"
    assert header.exists()
    text = header.read_text()
    assert "struct MyFilter" in text
    assert "GR_REGISTER_BLOCK" in text
    assert "GR_MAKE_REFLECTABLE" in text


def test_newblock_creates_test(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    test = project.group_test_dir("basic") / "qa_MyFilter.cpp"
    assert test.exists()
    text = test.read_text()
    assert "MyFilter" in text
    assert "boost::ut" in text


def test_newblock_updates_cmake(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    cmake = project.group_test_dir("basic") / "CMakeLists.txt"
    text = cmake.read_text()
    assert "qa_MyFilter" in text


def test_newblock_multi_output(project: ProjectConfig) -> None:
    answers = {
        "group_name": "basic",
        "block_name": "SplitBlock",
        "description": "Splits into two outputs.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out_a", "type": "T"}, {"name": "out_b", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": True,
    }
    write_block_files(project, answers)
    header = project.group_include_dir("basic") / "SplitBlock.hpp"
    text = header.read_text()
    assert "std::tuple" in text


def test_newblock_complex_ports(project: ProjectConfig) -> None:
    answers = {
        "group_name": "basic",
        "block_name": "ComplexGain",
        "description": "Multiplies complex samples by a scalar.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "std::complex<T>"}],
        "out_ports": [{"name": "out", "type": "std::complex<T>"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": True,
    }
    write_block_files(project, answers)
    header = project.group_include_dir("basic") / "ComplexGain.hpp"
    text = header.read_text()
    assert "#include <complex>" in text
    assert "std::complex<T>" in text


def test_newblock_no_test(project: ProjectConfig) -> None:
    answers = _basic_answers(block="HeaderOnly")
    answers["gen_test"] = False
    write_block_files(project, answers)
    test = project.group_test_dir("basic") / "qa_HeaderOnly.cpp"
    assert not test.exists()
