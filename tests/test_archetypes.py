"""Tests for block archetypes."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.newblock import ARCHETYPES, write_block_files
from gr4_modtool.commands.newgroup import write_group_skeleton
from gr4_modtool.project.discovery import ProjectConfig, save_config


@pytest.fixture()
def cfg(tmp_path: Path) -> ProjectConfig:
    c = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(c)
    (tmp_path / "blocks").mkdir()
    write_group_skeleton(c, "basic")
    return c


def _make_answers(cfg, archetype: str, block_name: str = "MyBlock") -> dict:
    arch = ARCHETYPES[archetype]
    return {
        "group_name": "basic",
        "block_name": block_name,
        "description": f"A {archetype} block",
        "template_params": ["T"],
        "in_ports": arch["in_ports"],
        "out_ports": arch["out_ports"],
        "processing_style": arch["processing_style"],
        "type_list": "float, double",
        "gen_test": False,
    }


def test_source_archetype_no_input_ports(cfg: ProjectConfig) -> None:
    answers = _make_answers(cfg, "source", "MySrc")
    write_block_files(cfg, answers)
    text = (cfg.group_include_dir("basic") / "MySrc.hpp").read_text()
    assert "PortIn" not in text


def test_sink_archetype_no_output_ports(cfg: ProjectConfig) -> None:
    answers = _make_answers(cfg, "sink", "MySink")
    write_block_files(cfg, answers)
    text = (cfg.group_include_dir("basic") / "MySink.hpp").read_text()
    assert "PortOut" not in text


def test_sync_archetype_processone(cfg: ProjectConfig) -> None:
    answers = _make_answers(cfg, "sync", "MyFilter")
    write_block_files(cfg, answers)
    text = (cfg.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "processOne" in text


def test_decimator_archetype_processbulk(cfg: ProjectConfig) -> None:
    answers = _make_answers(cfg, "decimator", "MyDec")
    write_block_files(cfg, answers)
    text = (cfg.group_include_dir("basic") / "MyDec.hpp").read_text()
    assert "processBulk" in text


def test_source_archetype_has_output_port(cfg: ProjectConfig) -> None:
    answers = _make_answers(cfg, "source", "MySrc2")
    write_block_files(cfg, answers)
    text = (cfg.group_include_dir("basic") / "MySrc2.hpp").read_text()
    assert "PortOut" in text


def test_custom_archetype_uses_provided_ports(cfg: ProjectConfig) -> None:
    answers = {
        "group_name": "basic",
        "block_name": "MyCustom",
        "description": "A custom block",
        "template_params": ["T"],
        "in_ports": [{"name": "a", "type": "T"}, {"name": "b", "type": "T"}],
        "out_ports": [{"name": "c", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float",
        "gen_test": False,
    }
    write_block_files(cfg, answers)
    text = (cfg.group_include_dir("basic") / "MyCustom.hpp").read_text()
    assert "PortIn" in text
    assert "PortOut" in text
    assert "processOne" in text


def test_archetypes_dict_has_all_keys() -> None:
    for name in ("source", "sink", "sync", "sync_bulk", "decimator", "interpolator"):
        assert name in ARCHETYPES
        arch = ARCHETYPES[name]
        assert "in_ports" in arch
        assert "out_ports" in arch
        assert "processing_style" in arch
