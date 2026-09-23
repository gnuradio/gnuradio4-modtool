"""Tests for export-spec command."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from gr4_modtool.commands.export_spec import (
    export_spec,
    header_to_spec_entry,
    infer_archetype,
)
from gr4_modtool.commands.newblock import load_spec, write_block_files
from gr4_modtool.project.discovery import ProjectConfig

# ---------------------------------------------------------------------------
# infer_archetype
# ---------------------------------------------------------------------------


def test_infer_archetype_sync() -> None:
    result = infer_archetype(
        [{"name": "in", "type": "T"}],
        [{"name": "out", "type": "T"}],
        "processOne",
    )
    assert result == "sync"


def test_infer_archetype_source() -> None:
    result = infer_archetype([], [{"name": "out", "type": "T"}], "processBulk")
    assert result == "source"


def test_infer_archetype_sink() -> None:
    result = infer_archetype([{"name": "in", "type": "T"}], [], "processBulk")
    assert result == "sink"


def test_infer_archetype_none_custom_ports() -> None:
    result = infer_archetype(
        [{"name": "in0", "type": "T"}, {"name": "in1", "type": "T"}],
        [{"name": "out", "type": "T"}],
        "processOne",
    )
    assert result is None


def test_infer_archetype_none_wrong_style() -> None:
    # sync ports but processBulk style → no exact match
    result = infer_archetype(
        [{"name": "in", "type": "T"}],
        [{"name": "out", "type": "T"}],
        "processBulk",
    )
    # decimator/interpolator/sync_bulk have the same ports+bulk style
    assert result in ("sync_bulk", "decimator", "interpolator")


# ---------------------------------------------------------------------------
# header_to_spec_entry
# ---------------------------------------------------------------------------


def test_header_to_spec_entry_sync_archetype(project: ProjectConfig, tmp_path: Path) -> None:
    answers = {
        "block_name": "MyFilter",
        "group_name": "basic",
        "description": "test filter",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": False,
        "simd": False,
    }
    write_block_files(project, answers)
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    entry = header_to_spec_entry(hpp, "basic")

    assert entry["block_name"] == "MyFilter"
    assert entry["group"] == "basic"
    assert entry["archetype"] == "sync"
    assert "in_ports" not in entry
    assert "out_ports" not in entry
    assert "processing_style" not in entry


def test_header_to_spec_entry_custom_ports(project: ProjectConfig, tmp_path: Path) -> None:
    answers = {
        "block_name": "DualIn",
        "group_name": "basic",
        "description": "",
        "template_params": ["T"],
        "in_ports": [{"name": "a", "type": "T"}, {"name": "b", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float",
        "gen_test": False,
        "simd": False,
    }
    write_block_files(project, answers)
    hpp = project.group_include_dir("basic") / "DualIn.hpp"
    entry = header_to_spec_entry(hpp, "basic")

    assert "archetype" not in entry
    assert len(entry["in_ports"]) == 2
    assert entry["processing_style"] == "processOne"


def test_header_to_spec_entry_invalid_raises(tmp_path: Path) -> None:
    bad = tmp_path / "notablock.hpp"
    bad.write_text("// just a header\n#pragma once\n")
    with pytest.raises(ValueError):
        header_to_spec_entry(bad, "basic")


# ---------------------------------------------------------------------------
# export_spec — output modes
# ---------------------------------------------------------------------------


def test_export_per_group_creates_yaml(project: ProjectConfig, tmp_path: Path) -> None:
    write_block_files(
        project,
        {
            "block_name": "Alpha",
            "group_name": "basic",
            "description": "",
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": "float",
            "gen_test": False,
            "simd": False,
        },
    )
    out_dir = tmp_path / "specs"
    written = export_spec(project, None, "per-group", out_dir)
    assert len(written) == 1
    assert written[0].name == "basic_blocks.yaml"
    assert written[0].exists()


def test_export_per_block_creates_yaml(project: ProjectConfig, tmp_path: Path) -> None:
    write_block_files(
        project,
        {
            "block_name": "Beta",
            "group_name": "basic",
            "description": "",
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": "float",
            "gen_test": False,
            "simd": False,
        },
    )
    out_dir = tmp_path / "specs"
    written = export_spec(project, None, "per-block", out_dir)
    assert len(written) == 1
    assert written[0].name == "Beta.yaml"
    assert (out_dir / "basic" / "Beta.yaml").exists()


def test_export_project_creates_single_yaml(project: ProjectConfig, tmp_path: Path) -> None:
    for name in ("Block1", "Block2"):
        write_block_files(
            project,
            {
                "block_name": name,
                "group_name": "basic",
                "description": "",
                "template_params": ["T"],
                "in_ports": [{"name": "in", "type": "T"}],
                "out_ports": [{"name": "out", "type": "T"}],
                "processing_style": "processOne",
                "type_list": "float",
                "gen_test": False,
                "simd": False,
            },
        )
    out_dir = tmp_path / "specs"
    written = export_spec(project, None, "project", out_dir)
    assert len(written) == 1
    assert written[0].name == "blocks.yaml"
    data = yaml.safe_load(written[0].read_text())
    assert isinstance(data, list)
    assert len(data) == 2


def test_export_group_filter(project_two_groups: ProjectConfig, tmp_path: Path) -> None:
    for group in ("basic", "filter"):
        write_block_files(
            project_two_groups,
            {
                "block_name": "FilterBlock" if group == "filter" else "BasicBlock",
                "group_name": group,
                "description": "",
                "template_params": ["T"],
                "in_ports": [{"name": "in", "type": "T"}],
                "out_ports": [{"name": "out", "type": "T"}],
                "processing_style": "processOne",
                "type_list": "float",
                "gen_test": False,
                "simd": False,
            },
        )
    out_dir = tmp_path / "specs"
    written = export_spec(project_two_groups, "basic", "per-group", out_dir)
    assert len(written) == 1
    assert written[0].name == "basic_blocks.yaml"
    data = yaml.safe_load(written[0].read_text())
    assert all(e["group"] == "basic" for e in data)


def test_export_returns_written_paths(project: ProjectConfig, tmp_path: Path) -> None:
    write_block_files(
        project,
        {
            "block_name": "Gamma",
            "group_name": "basic",
            "description": "",
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": "float",
            "gen_test": False,
            "simd": False,
        },
    )
    out_dir = tmp_path / "specs"
    written = export_spec(project, None, "per-group", out_dir)
    for p in written:
        assert isinstance(p, Path)
        assert p.exists()


def test_export_skips_non_block_headers(project: ProjectConfig, tmp_path: Path) -> None:
    # Write a legit block
    write_block_files(
        project,
        {
            "block_name": "Real",
            "group_name": "basic",
            "description": "",
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": "float",
            "gen_test": False,
            "simd": False,
        },
    )
    # Plant a non-block header in the include dir
    bad = project.group_include_dir("basic") / "NotABlock.hpp"
    bad.write_text("#pragma once\n// utility header, not a block\n")

    out_dir = tmp_path / "specs"
    written = export_spec(project, None, "per-group", out_dir)
    assert len(written) == 1
    data = yaml.safe_load(written[0].read_text())
    block_names = [e["block_name"] for e in data]
    assert "Real" in block_names
    assert "NotABlock" not in block_names


# ---------------------------------------------------------------------------
# roundtrip
# ---------------------------------------------------------------------------


def test_export_roundtrip(project: ProjectConfig, tmp_path: Path) -> None:
    """Write a block, export it, reload with load_spec — key fields survive."""
    original = {
        "block_name": "Roundtrip",
        "group_name": "basic",
        "description": "roundtrip test",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": False,
        "simd": False,
    }
    write_block_files(project, original)

    out_dir = tmp_path / "specs"
    written = export_spec(project, None, "project", out_dir)
    assert written

    entries = load_spec(written[0])
    assert len(entries) == 1
    e = entries[0]
    assert e["block_name"] == "Roundtrip"
    assert e["group_name"] == "basic"
    assert e["type_list"] == "float, double"
    assert e["processing_style"] == "processOne"
