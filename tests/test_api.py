"""Tests for gr4_modtool.api — public library surface."""

from __future__ import annotations

from pathlib import Path

import pytest

import gr4_modtool.api as api
from gr4_modtool.commands.newgroup import write_group_skeleton
from gr4_modtool.project.discovery import ProjectConfig, save_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path) -> ProjectConfig:
    cfg = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="1.2.3",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(cfg)
    (tmp_path / "blocks").mkdir()
    write_group_skeleton(cfg, "basic")
    return cfg


def _add_block(cfg: ProjectConfig, block_name: str, group: str = "basic") -> None:
    arch = api.ARCHETYPES["sync"]
    answers = {
        "group_name": group,
        "block_name": block_name,
        "description": f"Test {block_name}",
        "template_params": ["T"],
        "in_ports": arch["in_ports"],
        "out_ports": arch["out_ports"],
        "processing_style": arch["processing_style"],
        "type_list": "float, double",
        "gen_test": True,
        "simd": False,
    }
    api.write_block_files(cfg, answers)


# ---------------------------------------------------------------------------
# __all__ completeness
# ---------------------------------------------------------------------------


def test_api_all_symbols_importable() -> None:
    """Every name in __all__ can be imported from gr4_modtool.api."""
    for name in api.__all__:
        assert hasattr(api, name), f"api.__all__ lists {name!r} but it is not importable"


def test_api_all_is_defined() -> None:
    assert isinstance(api.__all__, list)
    assert len(api.__all__) > 0


# ---------------------------------------------------------------------------
# Project config
# ---------------------------------------------------------------------------


def test_find_project_root_finds_config(tmp_path: Path) -> None:
    _make_project(tmp_path)
    found = api.find_project_root(tmp_path)
    assert found == tmp_path


def test_find_project_root_from_subdir(tmp_path: Path) -> None:
    _make_project(tmp_path)
    subdir = tmp_path / "blocks" / "basic"
    found = api.find_project_root(subdir)
    assert found == tmp_path


def test_find_project_root_returns_none_when_absent(tmp_path: Path) -> None:
    assert api.find_project_root(tmp_path) is None


def test_load_config_returns_project_config(tmp_path: Path) -> None:
    _make_project(tmp_path)
    cfg = api.load_config(tmp_path)
    assert isinstance(cfg, api.ProjectConfig)
    assert cfg.name == "testmod"
    assert cfg.version == "1.2.3"


def test_save_config_roundtrip(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    cfg2 = api.load_config(tmp_path)
    assert cfg2.name == cfg.name
    assert cfg2.version == cfg.version
    assert cfg2.cmake_prefix == cfg.cmake_prefix


def test_discover_groups_returns_group_infos(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    groups = api.discover_groups(cfg)
    assert any(g.name == "basic" for g in groups)
    assert all(isinstance(g, api.GroupInfo) for g in groups)


def test_project_config_dataclass_fields() -> None:
    assert hasattr(api.ProjectConfig, "__dataclass_fields__")
    for field in ("name", "version", "root", "cmake_prefix", "groups"):
        assert field in api.ProjectConfig.__dataclass_fields__


def test_block_info_is_dataclass() -> None:
    assert hasattr(api.BlockInfo, "__dataclass_fields__")


def test_group_info_is_dataclass() -> None:
    assert hasattr(api.GroupInfo, "__dataclass_fields__")


# ---------------------------------------------------------------------------
# ARCHETYPES
# ---------------------------------------------------------------------------


def test_archetypes_is_dict() -> None:
    assert isinstance(api.ARCHETYPES, dict)


def test_archetypes_contains_expected_keys() -> None:
    for name in ("source", "sink", "sync", "sync_bulk", "decimator", "interpolator"):
        assert name in api.ARCHETYPES


def test_archetypes_entries_have_required_fields() -> None:
    for name, spec in api.ARCHETYPES.items():
        assert "in_ports" in spec, f"{name} missing in_ports"
        assert "out_ports" in spec, f"{name} missing out_ports"
        assert "processing_style" in spec, f"{name} missing processing_style"


# ---------------------------------------------------------------------------
# load_spec / validate_spec_entry
# ---------------------------------------------------------------------------


def test_load_spec_single_block(tmp_path: Path) -> None:
    spec = tmp_path / "block.yaml"
    spec.write_text("group: basic\nblock_name: MyFilter\narchetype: sync\ntype_list: 'float'\n")
    entries = api.load_spec(spec)
    assert len(entries) == 1
    assert entries[0]["block_name"] == "MyFilter"


def test_load_spec_list(tmp_path: Path) -> None:
    spec = tmp_path / "blocks.yaml"
    spec.write_text(
        "- group: basic\n  block_name: BlockA\n  archetype: sync\n  type_list: 'float'\n"
        "- group: basic\n  block_name: BlockB\n  archetype: sink\n  type_list: 'float'\n"
    )
    entries = api.load_spec(spec)
    assert len(entries) == 2
    names = {e["block_name"] for e in entries}
    assert names == {"BlockA", "BlockB"}


def test_load_spec_expands_archetype(tmp_path: Path) -> None:
    spec = tmp_path / "block.yaml"
    spec.write_text("group: basic\nblock_name: MySync\narchetype: sync\ntype_list: 'float'\n")
    entry = api.load_spec(spec)[0]
    assert entry["processing_style"] == "processOne"
    assert len(entry["in_ports"]) == 1
    assert len(entry["out_ports"]) == 1


def test_validate_spec_entry_raises_on_bad_name(tmp_path: Path) -> None:
    spec = tmp_path / "bad.yaml"
    spec.write_text("group: basic\nblock_name: bad_name\narchetype: sync\ntype_list: 'float'\n")
    entry = api.load_spec(spec)[0]
    with pytest.raises(ValueError, match="CamelCase"):
        api.validate_spec_entry(entry)


def test_validate_spec_entry_raises_missing_group(tmp_path: Path) -> None:
    spec = tmp_path / "bad.yaml"
    spec.write_text("block_name: MyFilter\narchetype: sync\ntype_list: 'float'\n")
    entry = api.load_spec(spec)[0]
    with pytest.raises(ValueError, match="group"):
        api.validate_spec_entry(entry)


# ---------------------------------------------------------------------------
# write_block_files
# ---------------------------------------------------------------------------


def test_write_block_files_creates_header(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "MyBlock")
    assert (cfg.group_include_dir("basic") / "MyBlock.hpp").exists()


def test_write_block_files_creates_test(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "MyBlock")
    assert (cfg.group_test_dir("basic") / "qa_MyBlock.cpp").exists()


def test_write_block_files_returns_paths(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    arch = api.ARCHETYPES["sink"]
    answers = {
        "group_name": "basic",
        "block_name": "MySink",
        "description": "",
        "template_params": ["T"],
        "in_ports": arch["in_ports"],
        "out_ports": arch["out_ports"],
        "processing_style": arch["processing_style"],
        "type_list": "float",
        "gen_test": False,
        "simd": False,
    }
    paths = api.write_block_files(cfg, answers)
    assert isinstance(paths, list)
    assert all(isinstance(p, Path) for p in paths)
    assert any(p.suffix == ".hpp" for p in paths)


# ---------------------------------------------------------------------------
# write_group_skeleton
# ---------------------------------------------------------------------------


def test_write_group_skeleton_creates_directories(tmp_path: Path) -> None:
    root2 = tmp_path / "proj2"
    root2.mkdir()
    cfg2 = ProjectConfig(
        root=root2,
        name="mod2",
        version="0.1.0",
        cpp_namespace="gr::mod2",
        cmake_prefix="gr4_mod2",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"dsp": "blocks/dsp"},
    )
    save_config(cfg2)
    (cfg2.root / "blocks").mkdir(parents=True)
    api.write_group_skeleton(cfg2, "dsp")
    assert cfg2.group_include_dir("dsp").exists()
    assert cfg2.group_test_dir("dsp").exists()


# ---------------------------------------------------------------------------
# infer_archetype / header_to_spec_entry
# ---------------------------------------------------------------------------


def test_infer_archetype_sync() -> None:
    result = api.infer_archetype(
        [{"name": "in", "type": "T"}],
        [{"name": "out", "type": "T"}],
        "processOne",
    )
    assert result == "sync"


def test_infer_archetype_source() -> None:
    result = api.infer_archetype([], [{"name": "out", "type": "T"}], "processBulk")
    assert result == "source"


def test_infer_archetype_returns_none_for_unknown() -> None:
    result = api.infer_archetype(
        [{"name": "a", "type": "T"}, {"name": "b", "type": "T"}],
        [{"name": "out", "type": "T"}],
        "processOne",
    )
    assert result is None


def test_header_to_spec_entry_roundtrip(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "RoundTrip")
    hpp = cfg.group_include_dir("basic") / "RoundTrip.hpp"
    entry = api.header_to_spec_entry(hpp, "basic")
    assert entry["block_name"] == "RoundTrip"
    assert entry["group"] == "basic"


# ---------------------------------------------------------------------------
# export_spec
# ---------------------------------------------------------------------------


def test_export_spec_writes_yaml(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Exported")
    out_dir = tmp_path / "specs"
    written = api.export_spec(cfg, group_filter=None, output="per-group", out_dir=out_dir)
    assert len(written) > 0
    assert all(p.suffix == ".yaml" for p in written)


# ---------------------------------------------------------------------------
# lint_header / lint_headers
# ---------------------------------------------------------------------------


def test_lint_header_clean_block(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Clean")
    hpp = cfg.group_include_dir("basic") / "Clean.hpp"
    issues = api.lint_header(hpp, "basic")
    assert all(i.severity != "error" for i in issues)


def test_lint_headers_returns_lint_issues(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Linted")
    issues = api.lint_headers(cfg)
    assert isinstance(issues, list)
    assert all(isinstance(i, api.LintIssue) for i in issues)


def test_lint_issue_is_dataclass() -> None:
    assert hasattr(api.LintIssue, "__dataclass_fields__")


# ---------------------------------------------------------------------------
# audit_project
# ---------------------------------------------------------------------------


def test_audit_project_clean(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Audited")
    issues = api.audit_project(cfg)
    assert isinstance(issues, list)
    assert all(isinstance(i, api.BlockIssue) for i in issues)
    assert issues == []


def test_audit_project_detects_missing_cmake(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Missing")
    cmake = cfg.group_test_dir("basic") / "CMakeLists.txt"
    text = cmake.read_text()
    cmake.write_text("\n".join(line for line in text.splitlines() if "Missing" not in line))
    issues = api.audit_project(cfg)
    assert any("Missing" in i.block for i in issues)


def test_block_issue_is_dataclass() -> None:
    assert hasattr(api.BlockIssue, "__dataclass_fields__")


# ---------------------------------------------------------------------------
# apply_version_bump
# ---------------------------------------------------------------------------


def test_apply_version_bump_updates_config(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    api.apply_version_bump(cfg, "2.0.0")
    updated = api.load_config(tmp_path)
    assert updated.version == "2.0.0"


def test_apply_version_bump_returns_paths(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    paths = api.apply_version_bump(cfg, "1.3.0")
    assert isinstance(paths, list)
    assert any(p.name == ".gr4modtool.toml" for p in paths)


# ---------------------------------------------------------------------------
# collect_inventory
# ---------------------------------------------------------------------------


def test_collect_inventory_returns_dict(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    data = api.collect_inventory(cfg)
    assert isinstance(data, dict)
    assert "project" in data
    assert "groups" in data


def test_collect_inventory_project_meta(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    data = api.collect_inventory(cfg)
    assert data["project"]["name"] == "testmod"
    assert data["project"]["version"] == "1.2.3"
    assert data["project"]["namespace"] == "gr::testmod"


def test_collect_inventory_lists_blocks(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Listed")
    data = api.collect_inventory(cfg)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert any(b["name"] == "Listed" for b in basic["blocks"])


def test_collect_inventory_group_filter(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Listed")
    data = api.collect_inventory(cfg, group_filter="basic")
    assert len(data["groups"]) == 1
    assert data["groups"][0]["name"] == "basic"


def test_collect_inventory_group_filter_excludes_others(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    data = api.collect_inventory(cfg, group_filter="nonexistent")
    assert data["groups"] == []


def test_collect_inventory_exclude_blocks(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Listed")
    data = api.collect_inventory(cfg, include_blocks=False)
    basic = next(g for g in data["groups"] if g["name"] == "basic")
    assert basic["blocks"] == []


# ---------------------------------------------------------------------------
# validate_project / ValidationIssue
# ---------------------------------------------------------------------------


def test_validation_issue_is_dataclass() -> None:
    assert hasattr(api.ValidationIssue, "__dataclass_fields__")
    for field in ("category", "group", "subject", "check", "detail", "severity"):
        assert field in api.ValidationIssue.__dataclass_fields__


def test_validate_project_clean(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Clean")
    issues = api.validate_project(cfg)
    assert isinstance(issues, list)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []


def test_validate_project_returns_validation_issues(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "Checked")
    issues = api.validate_project(cfg)
    assert all(isinstance(i, api.ValidationIssue) for i in issues)


def test_validate_project_detects_missing_pragma(tmp_path: Path) -> None:
    cfg = _make_project(tmp_path)
    _add_block(cfg, "NoPragma")
    hpp = cfg.group_include_dir("basic") / "NoPragma.hpp"
    text = hpp.read_text()
    hpp.write_text(text.replace("#pragma once", ""))
    issues = api.validate_project(cfg)
    h1 = [i for i in issues if i.check == "H1"]
    assert len(h1) > 0
