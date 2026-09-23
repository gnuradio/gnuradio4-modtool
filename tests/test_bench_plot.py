"""Tests for newbench --plot (Python plotting companion script)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.newbench import write_bench_file, write_plot_script
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.newgroup import write_group_skeleton
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
    return cfg


def test_plot_script_created(project_with_block: ProjectConfig) -> None:
    written = write_plot_script(project_with_block, "basic", "MyFilter")
    assert len(written) == 1
    assert written[0].name == "plot_MyFilter.py"
    assert written[0].exists()


def test_plot_script_has_matplotlib(project_with_block: ProjectConfig) -> None:
    write_plot_script(project_with_block, "basic", "MyFilter")
    text = (project_with_block.group_bench_dir("basic") / "plot_MyFilter.py").read_text()
    assert "matplotlib" in text


def test_plot_script_has_subprocess(project_with_block: ProjectConfig) -> None:
    write_plot_script(project_with_block, "basic", "MyFilter")
    text = (project_with_block.group_bench_dir("basic") / "plot_MyFilter.py").read_text()
    assert "subprocess" in text


def test_write_bench_with_plot_flag(project_with_block: ProjectConfig) -> None:
    written = write_bench_file(project_with_block, "basic", "MyFilter", write_plot=True)
    names = {p.name for p in written}
    assert "bench_MyFilter.cpp" in names
    assert "plot_MyFilter.py" in names
