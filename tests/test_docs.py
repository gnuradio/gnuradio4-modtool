"""Tests for the docs command (Doxyfile and block catalog)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.docs import build_catalog, write_doxyfile
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.newgroup import write_group_skeleton
from gr4_modtool.project.discovery import ProjectConfig, save_config


@pytest.fixture()
def cfg(tmp_path: Path) -> ProjectConfig:
    c = ProjectConfig(
        root=tmp_path,
        name="mymod",
        version="0.2.0",
        cpp_namespace="gr::mymod",
        cmake_prefix="gr4_mymod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(c)
    (tmp_path / "blocks").mkdir()
    write_group_skeleton(c, "basic")
    write_block_files(
        c,
        {
            "group_name": "basic",
            "block_name": "MyFilter",
            "description": "A test filter",
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": "float, double",
            "gen_test": False,
        },
    )
    return c


def test_doxyfile_created(cfg: ProjectConfig) -> None:
    written = write_doxyfile(cfg)
    assert len(written) == 1
    assert written[0].name == "Doxyfile"
    assert written[0].exists()


def test_doxyfile_has_project_name(cfg: ProjectConfig) -> None:
    write_doxyfile(cfg)
    text = (cfg.root / "Doxyfile").read_text()
    assert "mymod" in text


def test_doxyfile_has_input_dir(cfg: ProjectConfig) -> None:
    write_doxyfile(cfg)
    text = (cfg.root / "Doxyfile").read_text()
    assert "INPUT" in text
    assert "include" in text


def test_catalog_has_block_name(cfg: ProjectConfig) -> None:
    catalog = build_catalog(cfg)
    assert "MyFilter" in catalog


def test_catalog_has_markdown_table_header(cfg: ProjectConfig) -> None:
    catalog = build_catalog(cfg)
    assert "| Group |" in catalog
    assert "| Block |" in catalog
