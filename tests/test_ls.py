"""Tests for the list / ls command."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner
from rich.console import Console

from gr4_modtool.commands.ls import (
    _render_json,
    _render_table,
    _render_toml,
    _render_yaml,
    cmd,
    collect_inventory,
)
from gr4_modtool.project.discovery import ProjectConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FILTER_HEADER = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod::basic {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK({name}, 1, 1, [float, double])
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod::basic
"""


def _write_block(cfg: ProjectConfig, group: str, name: str) -> Path:
    inc = cfg.group_include_dir(group)
    inc.mkdir(parents=True, exist_ok=True)
    p = inc / f"{name}.hpp"
    p.write_text(_FILTER_HEADER.format(name=name))
    return p


def _write_test(cfg: ProjectConfig, group: str, block_name: str) -> Path:
    d = cfg.group_test_dir(group)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"qa_{block_name}.cpp"
    p.write_text("// test stub\n")
    return p


def _write_bench(cfg: ProjectConfig, group: str, block_name: str) -> Path:
    d = cfg.group_bench_dir(group)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"bench_{block_name}.cpp"
    p.write_text("// bench stub\n")
    return p


# ---------------------------------------------------------------------------
# collect_inventory — unit tests
# ---------------------------------------------------------------------------


def test_empty_project(project: ProjectConfig) -> None:
    data = collect_inventory(project)
    assert any(g["name"] == "basic" for g in data["groups"])
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert basic["blocks"] == []


def test_single_block_no_test(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    data = collect_inventory(project)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert len(basic["blocks"]) == 1
    b = basic["blocks"][0]
    assert b["name"] == "MyFilter"
    assert b["has_test"] is False
    assert b["test_path"] is None


def test_block_with_test(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_test(project, "basic", "MyFilter")
    data = collect_inventory(project)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    b = basic["blocks"][0]
    assert b["has_test"] is True
    assert b["test_path"] is not None
    assert "qa_MyFilter.cpp" in b["test_path"]


def test_block_with_bench(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_bench(project, "basic", "MyFilter")
    data = collect_inventory(project)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    b = basic["blocks"][0]
    assert b["has_bench"] is True
    assert b["bench_path"] is not None
    assert "bench_MyFilter.cpp" in b["bench_path"]


def test_no_bench_when_absent(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    data = collect_inventory(project)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert basic["blocks"][0]["has_bench"] is False
    assert basic["blocks"][0]["bench_path"] is None


def test_group_filter(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    _write_block(cfg, "basic", "BlockA")
    _write_block(cfg, "filter", "BlockB")
    data = collect_inventory(cfg, group_filter="basic")
    assert len(data["groups"]) == 1
    assert data["groups"][0]["name"] == "basic"


def test_project_meta(project: ProjectConfig) -> None:
    data = collect_inventory(project)
    proj = data["project"]
    assert proj["name"] == "testmod"
    assert proj["version"] == "0.1.0"
    assert proj["namespace"] == "gr::testmod"
    assert proj["cmake_prefix"] == "gr4_testmod"
    assert proj["build_cmake"] is True
    assert proj["flat_mode"] is False


def test_verbose_includes_ports(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    data = collect_inventory(project, verbose=True)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    b = basic["blocks"][0]
    assert "in_ports" in b
    assert "out_ports" in b
    assert "template_params" in b
    assert "processing_style" in b
    assert "namespace" in b


def test_non_verbose_omits_ports(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    data = collect_inventory(project, verbose=False)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    b = basic["blocks"][0]
    assert "in_ports" not in b
    assert "out_ports" not in b


def test_tests_section(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_test(project, "basic", "MyFilter")
    data = collect_inventory(project)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert len(basic["tests"]) == 1
    t = basic["tests"][0]
    assert t["name"] == "qa_MyFilter"
    assert t["block"] == "MyFilter"
    assert "qa_MyFilter.cpp" in t["path"]


def test_benchmarks_section(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_bench(project, "basic", "MyFilter")
    data = collect_inventory(project)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert len(basic["benchmarks"]) == 1
    bm = basic["benchmarks"][0]
    assert bm["name"] == "bench_MyFilter"
    assert bm["block"] == "MyFilter"
    assert "bench_MyFilter.cpp" in bm["path"]


def test_include_blocks_false(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    data = collect_inventory(project, include_blocks=False)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert basic["blocks"] == []


def test_include_tests_false(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_test(project, "basic", "MyFilter")
    data = collect_inventory(project, include_tests=False)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert basic["tests"] == []


def test_include_benchmarks_false(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_bench(project, "basic", "MyFilter")
    data = collect_inventory(project, include_benchmarks=False)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert basic["benchmarks"] == []


def test_unmatched_test(project: ProjectConfig) -> None:
    _write_test(project, "basic", "OrphanBlock")
    data = collect_inventory(project)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert len(basic["tests"]) == 1
    assert basic["tests"][0]["block"] == ""


def test_relative_paths(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    data = collect_inventory(project)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    header = basic["blocks"][0]["header"]
    assert not header.startswith(str(project.root))


# ---------------------------------------------------------------------------
# Format renderers
# ---------------------------------------------------------------------------


def test_json_parses(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    parsed = json.loads(_render_json(collect_inventory(project)))
    assert "project" in parsed
    assert "groups" in parsed


def test_json_has_project_key(project: ProjectConfig) -> None:
    parsed = json.loads(_render_json(collect_inventory(project)))
    assert parsed["project"]["name"] == "testmod"


def test_json_block_name(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    assert "MyFilter" in _render_json(collect_inventory(project))


def test_yaml_parses(project: ProjectConfig) -> None:
    pytest.importorskip("yaml")
    import yaml

    _write_block(project, "basic", "MyFilter")
    parsed = yaml.safe_load(_render_yaml(collect_inventory(project)))
    assert "project" in parsed
    assert "groups" in parsed


def test_yaml_group_filter(project_two_groups: ProjectConfig) -> None:
    pytest.importorskip("yaml")
    import yaml

    cfg = project_two_groups
    _write_block(cfg, "basic", "BlockA")
    _write_block(cfg, "filter", "BlockB")
    data = collect_inventory(cfg, group_filter="basic")
    parsed = yaml.safe_load(_render_yaml(data))
    assert len(parsed["groups"]) == 1
    assert parsed["groups"][0]["name"] == "basic"


def test_toml_parses(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    parsed = tomllib.loads(_render_toml(collect_inventory(project)))
    assert "project" in parsed


def test_toml_block_has_group_field(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    parsed = tomllib.loads(_render_toml(collect_inventory(project)))
    assert "blocks" in parsed
    assert parsed["blocks"][0]["group"] == "basic"


def test_toml_verbose_ports_parse(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    data = collect_inventory(project, verbose=True)
    parsed = tomllib.loads(_render_toml(data))
    b = parsed["blocks"][0]
    assert "in_ports" in b
    assert "out_ports" in b


def test_table_contains_block_name(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    console = Console(record=True, no_color=True)
    _render_table(collect_inventory(project), console)
    assert "MyFilter" in console.export_text()


def test_table_shows_test_tick(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_test(project, "basic", "MyFilter")
    console = Console(record=True, no_color=True)
    _render_table(collect_inventory(project), console)
    output = console.export_text()
    assert "MyFilter" in output
    assert "✓" in output


def test_table_shows_dash_when_no_test(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter")
    console = Console(record=True, no_color=True)
    _render_table(collect_inventory(project), console)
    output = console.export_text()
    assert "MyFilter" in output
    assert "–" in output


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_cli_default_exits_0(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert "MyFilter" in result.output


def test_cli_json_flag(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--json", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["project"]["name"] == "testmod"


def test_cli_yaml_flag(project: ProjectConfig, runner: CliRunner) -> None:
    pytest.importorskip("yaml")
    import yaml

    _write_block(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--yaml", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert "project" in yaml.safe_load(result.output)


def test_cli_toml_flag(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--toml", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert tomllib.loads(result.output)["project"]["name"] == "testmod"


def test_cli_format_json(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--format", "json", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert "groups" in json.loads(result.output)


def test_cli_group_filter(project_two_groups: ProjectConfig, runner: CliRunner) -> None:
    cfg = project_two_groups
    _write_block(cfg, "basic", "BlockA")
    _write_block(cfg, "filter", "BlockB")
    result = runner.invoke(cmd, ["--json", "--group", "basic", "--project-dir", str(cfg.root)])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert len(parsed["groups"]) == 1
    assert parsed["groups"][0]["name"] == "basic"


def test_cli_no_tests(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_test(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--json", "--no-tests", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert json.loads(result.output)["groups"][0]["tests"] == []


def test_cli_no_benchmarks(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter")
    _write_bench(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--json", "--no-benchmarks", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert json.loads(result.output)["groups"][0]["benchmarks"] == []


def test_cli_no_blocks(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--json", "--no-blocks", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert json.loads(result.output)["groups"][0]["blocks"] == []


def test_cli_conflict_json_yaml(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--json", "--yaml", "--project-dir", str(project.root)])
    assert result.exit_code != 0


def test_cli_conflict_format_and_flag(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--format", "json", "--toml", "--project-dir", str(project.root)])
    assert result.exit_code != 0


def test_cli_alias_ls(project: ProjectConfig, runner: CliRunner) -> None:
    from gr4_modtool.cli import cli

    _write_block(project, "basic", "MyFilter")
    result = runner.invoke(cli, ["ls", "--json", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert json.loads(result.output)["project"]["name"] == "testmod"
