"""E2E: grouped project command sequences.

Each test exercises multiple commands in sequence against the same project
tree.  The project fixture provides a well-formed starting state; commands are
invoked through the real CLI entry point.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec

# ---------------------------------------------------------------------------
# newblock → check
# ---------------------------------------------------------------------------


def test_newblock_then_check_is_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """After newblock the project passes check with no errors."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "check", "--json")
    data = json.loads(result.output)
    assert data["error_count"] == 0


def test_newblock_creates_header_and_test(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock via CLI writes both the header and qa_*.cpp test source."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    assert (project.group_include_dir("basic") / "MyFilter.hpp").exists()
    assert (project.group_test_dir("basic") / "qa_MyFilter.cpp").exists()


def test_newblock_registers_in_cmake(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock adds the block's qa_* entry to CMakeLists.txt."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    cmake = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "MyFilter" in cmake


# ---------------------------------------------------------------------------
# newblock → info
# ---------------------------------------------------------------------------


def test_info_json_contains_newblock(project: ProjectConfig, tmp_path: Path) -> None:
    """info --json lists the block created by newblock."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "info", "--json")
    data = json.loads(result.output)
    group_data = next(g for g in data["groups"] if g["name"] == "basic")
    block_names = [b["name"] for b in group_data["blocks"]]
    assert "MyFilter" in block_names


def test_status_shows_newblock(project: ProjectConfig, tmp_path: Path) -> None:
    """status output mentions the block created by newblock."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "status")
    assert "MyFilter" in result.output or "basic" in result.output


# ---------------------------------------------------------------------------
# check → sync → check cycle
# ---------------------------------------------------------------------------


def test_sync_fixes_missing_cmake_entry(project: ProjectConfig, tmp_path: Path) -> None:
    """Deleting a CMake entry is detected by check and repaired by sync."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    # Corrupt: remove the cmake entry manually
    cmake = project.group_test_dir("basic") / "CMakeLists.txt"
    original = cmake.read_text()
    cmake.write_text(
        "\n".join(line for line in original.splitlines() if "MyFilter" not in line) + "\n"
    )

    # check should now report an error
    result = invoke(project.root, "check", "--json", expect_ok=False)
    assert json.loads(result.output)["error_count"] > 0

    # sync should fix it
    invoke(project.root, "sync", "--yes")

    # check should be clean again
    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_sync_dry_run_does_not_modify(project: ProjectConfig, tmp_path: Path) -> None:
    """sync --dry-run exits 0 but does not write any files."""
    spec = write_spec(tmp_path / "spec.yaml", "Orphan", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    cmake = project.group_test_dir("basic") / "CMakeLists.txt"
    original = cmake.read_text()
    cmake.write_text(
        "\n".join(line for line in original.splitlines() if "Orphan" not in line) + "\n"
    )
    before = cmake.read_text()

    invoke(project.root, "sync", "--dry-run")

    assert cmake.read_text() == before


# ---------------------------------------------------------------------------
# newblock → newgroup → second block → check
# ---------------------------------------------------------------------------


def test_newgroup_then_newblock_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """Adding a new group and a block in it passes check."""
    invoke(project.root, "newgroup", "--name", "filter")

    spec = write_spec(tmp_path / "spec.yaml", "LowPass", group="filter")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_info_json_shows_multiple_groups(project: ProjectConfig, tmp_path: Path) -> None:
    """info --json lists all groups after newgroup."""
    invoke(project.root, "newgroup", "--name", "filter")

    result = invoke(project.root, "info", "--json")
    group_names = [g["name"] for g in json.loads(result.output)["groups"]]
    assert "basic" in group_names
    assert "filter" in group_names


# ---------------------------------------------------------------------------
# export-spec roundtrip
# ---------------------------------------------------------------------------


def test_export_spec_roundtrip(project: ProjectConfig, tmp_path: Path) -> None:
    """export-spec produces a YAML that newblock --spec recreates the block."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    out_dir = project.root / "specs"
    invoke(project.root, "export-spec", "--group", "basic", "--out-dir", str(out_dir))
    spec_files = list(out_dir.glob("*.yaml"))
    assert spec_files, "export-spec wrote no YAML files"

    # Re-create in a second project using the exported spec
    from gr4_modtool.commands.newgroup import write_group_skeleton
    from gr4_modtool.project.discovery import ProjectConfig, save_config

    (tmp_path / "proj2").mkdir()
    cfg2 = ProjectConfig(
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

    invoke(cfg2.root, "newblock", "--spec", str(spec_files[0]))
    assert (cfg2.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_export_spec_multi_block_roundtrip(project: ProjectConfig, tmp_path: Path) -> None:
    """export-spec (per-group) produces a list YAML for two blocks; reimporting it is clean.

    This exercises both the list-export path in export_spec and the multi-block spec
    import path in load_spec, all through the real CLI.
    """
    from gr4_modtool.commands.newgroup import write_group_skeleton
    from gr4_modtool.project.discovery import ProjectConfig as PC
    from gr4_modtool.project.discovery import save_config

    for name, arch in (("BlockOne", "sync"), ("BlockTwo", "sink")):
        spec = write_spec(tmp_path / f"spec_{name}.yaml", name, group="basic", archetype=arch)
        invoke(project.root, "newblock", "--spec", str(spec))

    # per-group (default) writes one file per group — a YAML list when >1 block
    out_dir = project.root / "specs"
    invoke(project.root, "export-spec", "--group", "basic", "--out-dir", str(out_dir))
    spec_files = list(out_dir.glob("*.yaml"))
    assert len(spec_files) == 1, "per-group export should produce exactly one file"

    # Re-import that list spec into a fresh project
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

    invoke(cfg2.root, "newblock", "--spec", str(spec_files[0]))

    assert (cfg2.group_include_dir("basic") / "BlockOne.hpp").exists()
    assert (cfg2.group_include_dir("basic") / "BlockTwo.hpp").exists()
    result = invoke(cfg2.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# sync --prune and group filter
# ---------------------------------------------------------------------------


def test_sync_prune_removes_stale_cmake_entry(project: ProjectConfig, tmp_path: Path) -> None:
    """sync --prune removes a cmake entry when both header and test source are deleted."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    # Delete header and test source — cmake entry is now fully stale
    (project.group_include_dir("basic") / "MyFilter.hpp").unlink()
    (project.group_test_dir("basic") / "qa_MyFilter.cpp").unlink()

    invoke(project.root, "sync", "--prune", "--yes")

    cmake = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "MyFilter" not in cmake


def test_sync_group_filter_only_affects_target_group(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """sync --group limits repairs to the specified group only."""
    invoke(project.root, "newgroup", "--name", "filter")

    spec_basic = write_spec(tmp_path / "spec_b.yaml", "BlockA", group="basic")
    spec_filter = write_spec(tmp_path / "spec_f.yaml", "BlockB", group="filter")
    invoke(project.root, "newblock", "--spec", str(spec_basic))
    invoke(project.root, "newblock", "--spec", str(spec_filter))

    # Break cmake entry in both groups
    for grp in ("basic", "filter"):
        cmake = project.group_test_dir(grp) / "CMakeLists.txt"
        cmake.write_text(
            "\n".join(line for line in cmake.read_text().splitlines() if "Block" not in line) + "\n"
        )

    # Only sync basic
    invoke(project.root, "sync", "--group", "basic", "--yes")

    basic_cmake = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    filter_cmake = (project.group_test_dir("filter") / "CMakeLists.txt").read_text()

    assert "BlockA" in basic_cmake
    assert "BlockB" not in filter_cmake


# ---------------------------------------------------------------------------
# Custom port spec (no archetype shorthand)
# ---------------------------------------------------------------------------


def test_newblock_custom_ports_spec(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock --spec with explicit in_ports/out_ports (no archetype) creates a valid block."""
    spec_path = tmp_path / "custom_spec.yaml"
    spec_path.write_text(
        "block_name: CustomFilter\n"
        "group: basic\n"
        "processing_style: processOne\n"
        'type_list: "float, double"\n'
        "in_ports:\n"
        "  - name: audio_in\n"
        "    type: T\n"
        "  - name: ctrl_in\n"
        "    type: float\n"
        "out_ports:\n"
        "  - name: audio_out\n"
        "    type: T\n"
        "gen_test: true\n"
    )
    invoke(project.root, "newblock", "--spec", str(spec_path))

    header = (project.group_include_dir("basic") / "CustomFilter.hpp").read_text()
    assert "audio_in" in header
    assert "ctrl_in" in header
    assert "audio_out" in header

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# Parametrized archetype coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "archetype", ["sync", "sync_bulk", "source", "sink", "decimator", "interpolator"]
)
def test_newblock_all_archetypes_check_clean(
    project: ProjectConfig, tmp_path: Path, archetype: str
) -> None:
    """newblock passes check for every supported archetype."""
    block_name = "My" + "".join(part.capitalize() for part in archetype.split("_")) + "Block"
    spec = write_spec(
        tmp_path / f"spec_{archetype}.yaml", block_name, group="basic", archetype=archetype
    )
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0
