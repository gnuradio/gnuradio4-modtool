"""Tests for newblock --spec YAML loading and block generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.newblock import (
    load_spec,
    validate_spec_entry,
    write_block_files,
)
from gr4_modtool.project.discovery import ProjectConfig


def _write_yaml(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# load_spec — single block
# ---------------------------------------------------------------------------


def test_spec_single_block_creates_header(project: ProjectConfig, tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
group: basic
block_name: MyFilter
type_list: "float, double"
archetype: sync
""",
    )
    entries = load_spec(spec)
    assert len(entries) == 1
    write_block_files(project, entries[0])
    assert (project.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_spec_single_block_creates_test(project: ProjectConfig, tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
group: basic
block_name: TestBlock
type_list: "float"
archetype: sync
gen_test: true
""",
    )
    entries = load_spec(spec)
    write_block_files(project, entries[0])
    assert (project.group_test_dir("basic") / "qa_TestBlock.cpp").exists()


# ---------------------------------------------------------------------------
# load_spec — multiple blocks
# ---------------------------------------------------------------------------


def test_spec_multiple_blocks(project: ProjectConfig, tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "blocks.yaml",
        """
- group: basic
  block_name: FilterA
  archetype: sync
  type_list: "float"

- group: basic
  block_name: FilterB
  archetype: sink
  type_list: "double"
""",
    )
    entries = load_spec(spec)
    assert len(entries) == 2
    for e in entries:
        write_block_files(project, e)
    assert (project.group_include_dir("basic") / "FilterA.hpp").exists()
    assert (project.group_include_dir("basic") / "FilterB.hpp").exists()


# ---------------------------------------------------------------------------
# group override
# ---------------------------------------------------------------------------


def test_spec_group_override(project: ProjectConfig, tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
group: basic
block_name: Overridden
archetype: sync
type_list: "float"
""",
    )
    # Override to the same group (basic exists in fixture); behaviour: group_name = override
    entries = load_spec(spec, group_override="basic")
    assert entries[0]["group_name"] == "basic"
    write_block_files(project, entries[0])
    assert (project.group_include_dir("basic") / "Overridden.hpp").exists()


# ---------------------------------------------------------------------------
# archetype expansion
# ---------------------------------------------------------------------------


def test_spec_archetype_fills_ports(tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
group: basic
block_name: AFilter
archetype: sync
type_list: "float"
""",
    )
    entries = load_spec(spec)
    e = entries[0]
    assert e["processing_style"] == "processOne"
    assert len(e["in_ports"]) == 1
    assert len(e["out_ports"]) == 1


def test_spec_archetype_explicit_ports_override(tmp_path: Path) -> None:
    """Explicit in_ports in YAML override the archetype's defaults."""
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
group: basic
block_name: CustomSource
archetype: source
in_ports:
  - {name: feedback, type: T}
type_list: "float"
""",
    )
    entries = load_spec(spec)
    e = entries[0]
    # archetype source has no in_ports, but explicit YAML adds one
    assert len(e["in_ports"]) == 1
    assert e["in_ports"][0]["name"] == "feedback"


# ---------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------


def test_spec_gen_test_defaults_true(tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
group: basic
block_name: Defaulted
archetype: sync
type_list: "float"
""",
    )
    entries = load_spec(spec)
    assert entries[0]["gen_test"] is True


def test_spec_template_params_defaults_to_T(tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
group: basic
block_name: Defaulted
archetype: sync
type_list: "float"
""",
    )
    entries = load_spec(spec)
    assert entries[0]["template_params"] == ["T"]


# ---------------------------------------------------------------------------
# validate_spec_entry
# ---------------------------------------------------------------------------


def test_spec_validation_invalid_name(tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
group: basic
block_name: my_filter
type_list: "float"
archetype: sync
""",
    )
    entries = load_spec(spec)
    with pytest.raises(ValueError, match="CamelCase"):
        validate_spec_entry(entries[0])


def test_spec_validation_missing_group(tmp_path: Path) -> None:
    spec = _write_yaml(
        tmp_path / "block.yaml",
        """
block_name: MyFilter
type_list: "float"
archetype: sync
""",
    )
    entries = load_spec(spec)
    with pytest.raises(ValueError, match="group"):
        validate_spec_entry(entries[0])
