"""Tests for show command."""

import pytest

from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.show import show_block
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


def test_show_displays_header_content(project: ProjectConfig, capsys) -> None:
    write_block_files(project, _basic_answers())
    show_block(project, "basic", "MyFilter")
    captured = capsys.readouterr()
    assert "MyFilter" in captured.out


def test_show_test_flag_shows_test(project: ProjectConfig, capsys) -> None:
    write_block_files(project, _basic_answers())
    show_block(project, "basic", "MyFilter", show_test=True)
    captured = capsys.readouterr()
    assert "MyFilter" in captured.out


def test_show_raises_if_block_missing(project: ProjectConfig) -> None:
    with pytest.raises(FileNotFoundError):
        show_block(project, "basic", "Ghost")


def test_show_raises_if_test_missing(project: ProjectConfig) -> None:
    write_block_files(project, {**_basic_answers(), "gen_test": False})
    with pytest.raises(FileNotFoundError):
        show_block(project, "basic", "MyFilter", show_test=True)
