"""Tests for info --verbose and --json --verbose."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from gr4_modtool.cli import cli
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.newgroup import write_group_skeleton
from gr4_modtool.commands.newparam import add_param
from gr4_modtool.project.discovery import ProjectConfig, save_config


@pytest.fixture()
def project_with_block(tmp_path: Path) -> ProjectConfig:
    cfg = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(cfg)
    (tmp_path / "blocks").mkdir()
    write_group_skeleton(cfg, "basic")

    write_block_files(
        cfg,
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

    add_param(cfg, "basic", "MyFilter", "gain", "float", "Gain factor", "1.0f")
    return cfg


def test_verbose_shows_ports(project_with_block: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli, ["info", "--project-dir", str(project_with_block.root), "--verbose"]
    )
    assert result.exit_code == 0
    assert "in" in result.output or "out" in result.output


def test_verbose_shows_params(project_with_block: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli, ["info", "--project-dir", str(project_with_block.root), "--verbose"]
    )
    assert result.exit_code == 0
    assert "gain" in result.output


def test_verbose_json_has_ports(project_with_block: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli, ["info", "--project-dir", str(project_with_block.root), "--json", "--verbose"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    block = data["groups"][0]["blocks"][0]
    assert "ports" in block
    assert "in" in block["ports"]
    assert "out" in block["ports"]


def test_verbose_json_has_params(project_with_block: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli, ["info", "--project-dir", str(project_with_block.root), "--json", "--verbose"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    block = data["groups"][0]["blocks"][0]
    assert "params" in block
    param_names = [p["name"] for p in block["params"]]
    assert "gain" in param_names


def test_verbose_empty_block_no_crash(tmp_path: Path) -> None:
    cfg = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(cfg)
    (tmp_path / "blocks").mkdir()
    write_group_skeleton(cfg, "basic")
    # Group with no blocks — should not crash
    runner = CliRunner()
    result = runner.invoke(cli, ["info", "--project-dir", str(tmp_path), "--verbose"])
    assert result.exit_code == 0
