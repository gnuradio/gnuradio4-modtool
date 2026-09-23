"""E2E: error paths and hostile input handling.

Tests that commands fail gracefully when given bad input, non-existent
targets, or conflicting options.
"""

from __future__ import annotations

from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec

# ---------------------------------------------------------------------------
# newblock — bad block names
# ---------------------------------------------------------------------------


def test_newblock_lowercase_name_errors(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock exits nonzero when the block name does not start with uppercase."""
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "block_name: myFilter\ngroup: basic\narchetype: filter\ntype_list: float\ngen_test: true\n"
    )

    result = invoke(project.root, "newblock", "--spec", str(spec), expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# newgroup — bad group names / duplicates
# ---------------------------------------------------------------------------


def test_newgroup_duplicate_errors(project: ProjectConfig) -> None:
    """newgroup exits nonzero when the group already exists."""
    result = invoke(project.root, "newgroup", "--name", "basic", expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# check — group filter on unknown group
# ---------------------------------------------------------------------------


def test_check_unknown_group_exits_ok(project: ProjectConfig) -> None:
    """check --group with a non-existent group name exits 0 with no issues."""
    result = invoke(project.root, "check", "--group", "nonexistent", "--json")
    import json

    data = json.loads(result.output)
    assert data["error_count"] == 0


# ---------------------------------------------------------------------------
# sync — dry-run does not mutate
# ---------------------------------------------------------------------------


def test_sync_dry_run_no_mutation(project: ProjectConfig, tmp_path: Path) -> None:
    """sync --dry-run never writes files even when issues exist."""
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
# show — missing group
# ---------------------------------------------------------------------------


def test_show_nonexistent_group_errors(project: ProjectConfig) -> None:
    """show exits nonzero when the group does not exist."""
    result = invoke(project.root, "show", "AnyBlock", "--group", "nonexistent", expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# newblock — spec file errors
# ---------------------------------------------------------------------------


def test_newblock_spec_missing_file_exits_nonzero(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock exits nonzero when --spec points to a file that does not exist."""
    result = invoke(
        project.root,
        "newblock",
        "--spec",
        str(tmp_path / "nonexistent.yaml"),
        expect_ok=False,
    )
    assert result.exit_code != 0


def test_newblock_spec_malformed_yaml_exits_nonzero(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock exits nonzero when the spec file contains invalid YAML."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("{{{not: valid: yaml\n")
    result = invoke(project.root, "newblock", "--spec", str(bad), expect_ok=False)
    assert result.exit_code != 0


def test_newblock_spec_unknown_archetype_exits_nonzero(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """newblock exits nonzero when the spec references an unknown archetype."""
    bad = tmp_path / "bad_arch.yaml"
    bad.write_text(
        "block_name: MyBlock\ngroup: basic\narchetype: bogus_archetype\ntype_list: float\n"
    )
    result = invoke(project.root, "newblock", "--spec", str(bad), expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# rm / add-dep — missing entity errors
# ---------------------------------------------------------------------------


def test_rm_nonexistent_group_exits_nonzero(project: ProjectConfig) -> None:
    """rm exits nonzero when the target group does not exist."""
    result = invoke(project.root, "rm", "--group", "phantom", "Ghost", "-y", expect_ok=False)
    assert result.exit_code != 0


def test_add_dep_missing_cmake_file_reports_error(project: ProjectConfig) -> None:
    """add-dep exits 0 but reports a cmake error when Dependencies.cmake is absent."""
    result = invoke(
        project.root,
        "add-dep",
        "FFTW3",
        "--pkg-config",
        "fftw3",
    )
    assert result.exit_code == 0
    assert "cmake" in result.output.lower() or "No files modified" in result.output
