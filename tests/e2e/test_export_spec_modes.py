"""E2E: export-spec --output per-block and --output project modes.

The per-group default is already tested in test_grouped_workflow.py.
This file covers the two remaining output modes:

  per-block  — one YAML file per block in out_dir/<group>/BlockName.yaml
  project    — one YAML file for all groups at out_dir/blocks.yaml
"""

from __future__ import annotations

import json
from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec


def _make_two_blocks(project: ProjectConfig, tmp_path: Path) -> None:
    """Add BlockOne (filter) and BlockTwo (sink) to the basic group."""
    for name, arch in (("BlockOne", "sync"), ("BlockTwo", "sink")):
        spec = write_spec(tmp_path / f"s_{name}.yaml", name, group="basic", archetype=arch)
        invoke(project.root, "newblock", "--spec", str(spec))


# ---------------------------------------------------------------------------
# per-block mode
# ---------------------------------------------------------------------------


def test_export_spec_per_block_creates_one_file_per_block(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """--output per-block creates a separate YAML for every block."""
    _make_two_blocks(project, tmp_path)

    out_dir = project.root / "specs"
    invoke(
        project.root,
        "export-spec",
        "--group",
        "basic",
        "--output",
        "per-block",
        "--out-dir",
        str(out_dir),
    )

    per_block_dir = out_dir / "basic"
    assert per_block_dir.is_dir()
    spec_files = list(per_block_dir.glob("*.yaml"))
    assert len(spec_files) == 2, f"expected 2 per-block files, got {len(spec_files)}"


def test_export_spec_per_block_filenames_match_blocks(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """--output per-block names each YAML after its block."""
    _make_two_blocks(project, tmp_path)

    out_dir = project.root / "specs"
    invoke(
        project.root,
        "export-spec",
        "--output",
        "per-block",
        "--out-dir",
        str(out_dir),
    )

    per_block_dir = out_dir / "basic"
    names = {f.stem for f in per_block_dir.glob("*.yaml")}
    assert "BlockOne" in names
    assert "BlockTwo" in names


def test_export_spec_per_block_roundtrip(project: ProjectConfig, tmp_path: Path) -> None:
    """Each per-block YAML can be reimported via newblock --spec into a fresh project."""
    from gr4_modtool.commands.newgroup import write_group_skeleton
    from gr4_modtool.project.discovery import ProjectConfig as PC
    from gr4_modtool.project.discovery import save_config

    _make_two_blocks(project, tmp_path)

    out_dir = project.root / "specs"
    invoke(
        project.root,
        "export-spec",
        "--output",
        "per-block",
        "--out-dir",
        str(out_dir),
    )

    (tmp_path / "proj2").mkdir()
    cfg2 = PC(
        root=tmp_path / "proj2",
        name="testmod2",
        version="0.1.0",
        cpp_namespace="gr::testmod2",
        cmake_prefix="gr4_testmod2",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(cfg2)
    write_group_skeleton(cfg2, "basic")

    for sf in sorted((out_dir / "basic").glob("*.yaml")):
        invoke(cfg2.root, "newblock", "--spec", str(sf))

    result = invoke(cfg2.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# project mode
# ---------------------------------------------------------------------------


def test_export_spec_project_creates_single_file(project: ProjectConfig, tmp_path: Path) -> None:
    """--output project writes a single blocks.yaml at the output root."""
    _make_two_blocks(project, tmp_path)

    out_dir = project.root / "specs"
    invoke(
        project.root,
        "export-spec",
        "--output",
        "project",
        "--out-dir",
        str(out_dir),
    )

    assert (out_dir / "blocks.yaml").exists()
    spec_files = list(out_dir.glob("*.yaml"))
    assert len(spec_files) == 1, "project mode should write exactly one file"


def test_export_spec_project_contains_all_blocks(project: ProjectConfig, tmp_path: Path) -> None:
    """blocks.yaml from --output project lists every block in the project."""
    import yaml

    _make_two_blocks(project, tmp_path)

    out_dir = project.root / "specs"
    invoke(
        project.root,
        "export-spec",
        "--output",
        "project",
        "--out-dir",
        str(out_dir),
    )

    entries = yaml.safe_load((out_dir / "blocks.yaml").read_text())
    assert isinstance(entries, list)
    names = {e["block_name"] for e in entries}
    assert {"BlockOne", "BlockTwo"}.issubset(names)


def test_export_spec_project_roundtrip(project: ProjectConfig, tmp_path: Path) -> None:
    """blocks.yaml from --output project is a valid multi-block spec importable via newblock."""
    from gr4_modtool.commands.newgroup import write_group_skeleton
    from gr4_modtool.project.discovery import ProjectConfig as PC
    from gr4_modtool.project.discovery import save_config

    _make_two_blocks(project, tmp_path)

    out_dir = project.root / "specs"
    invoke(
        project.root,
        "export-spec",
        "--output",
        "project",
        "--out-dir",
        str(out_dir),
    )

    (tmp_path / "proj2").mkdir()
    cfg2 = PC(
        root=tmp_path / "proj2",
        name="testmod2",
        version="0.1.0",
        cpp_namespace="gr::testmod2",
        cmake_prefix="gr4_testmod2",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(cfg2)
    write_group_skeleton(cfg2, "basic")

    invoke(cfg2.root, "newblock", "--spec", str(out_dir / "blocks.yaml"))

    assert (cfg2.group_include_dir("basic") / "BlockOne.hpp").exists()
    assert (cfg2.group_include_dir("basic") / "BlockTwo.hpp").exists()
    result = invoke(cfg2.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0
