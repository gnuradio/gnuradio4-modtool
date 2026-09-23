"""Tests for newparam command."""

import pytest

from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.newparam import add_param
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
        "gen_test": False,
    }


def test_newparam_adds_annotated_member(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    add_param(project, "basic", "MyFilter", "gain", "float", "Gain factor", "1.0f")
    text = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "Annotated<float" in text
    assert "gain" in text


def test_newparam_updates_gr_make_reflectable(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    add_param(project, "basic", "MyFilter", "gain", "float", "Gain factor", "1.0f")
    text = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "GR_MAKE_REFLECTABLE" in text
    # param_name must appear after the macro open-paren
    macro_line = next(line for line in text.splitlines() if "GR_MAKE_REFLECTABLE" in line)
    assert "gain" in macro_line


def test_newparam_description_in_doc(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    add_param(project, "basic", "MyFilter", "gain", "float", "Gain factor", "1.0f")
    text = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert '"gain", Doc<"Gain factor">' in text


def test_newparam_default_value_present(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    add_param(project, "basic", "MyFilter", "gain", "float", "Gain", "2.5f")
    text = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "2.5f" in text


def test_newparam_type_in_annotated(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    add_param(project, "basic", "MyFilter", "cutoff", "double", "Cutoff", "1000.0")
    text = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "Annotated<double" in text


def test_newparam_raises_if_header_missing(project: ProjectConfig) -> None:
    with pytest.raises(FileNotFoundError):
        add_param(project, "basic", "Ghost", "gain", "float", "Gain", "1.0f")


def test_newparam_raises_if_param_exists(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    add_param(project, "basic", "MyFilter", "gain", "float", "Gain", "1.0f")
    with pytest.raises(ValueError):
        add_param(project, "basic", "MyFilter", "gain", "float", "Gain again", "2.0f")
