"""E2E: block mutation command sequences (rename, rm, cp, mv, rename-group)."""

from __future__ import annotations

import json
from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec


def _add_block(
    project: ProjectConfig,
    tmp_path: Path,
    block_name: str = "MyFilter",
    group: str = "basic",
) -> None:
    """Add a block via newblock --spec through the CLI entry point."""
    spec = write_spec(tmp_path / f"spec_{block_name}.yaml", block_name, group=group)
    invoke(project.root, "newblock", "--spec", str(spec))


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------


def test_rename_block_moves_header(project: ProjectConfig, tmp_path: Path) -> None:
    """rename moves the header file and removes the old one."""
    _add_block(project, tmp_path)
    invoke(project.root, "rename", "--group", "basic", "MyFilter", "Booster", "-y")

    assert (project.group_include_dir("basic") / "Booster.hpp").exists()
    assert not (project.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_rename_block_updates_header_content(project: ProjectConfig, tmp_path: Path) -> None:
    """Renamed header contains the new struct name and not the old one."""
    _add_block(project, tmp_path)
    invoke(project.root, "rename", "--group", "basic", "MyFilter", "Booster", "-y")

    text = (project.group_include_dir("basic") / "Booster.hpp").read_text()
    assert "Booster" in text
    assert "MyFilter" not in text


def test_rename_block_updates_cmake(project: ProjectConfig, tmp_path: Path) -> None:
    """CMakeLists.txt references the new name after rename."""
    _add_block(project, tmp_path)
    invoke(project.root, "rename", "--group", "basic", "MyFilter", "Booster", "-y")

    cmake = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "Booster" in cmake
    assert "MyFilter" not in cmake


def test_rename_block_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check reports no errors after rename."""
    _add_block(project, tmp_path)
    invoke(project.root, "rename", "--group", "basic", "MyFilter", "Booster", "-y")

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------


def test_rm_removes_header(project: ProjectConfig, tmp_path: Path) -> None:
    """rm deletes the block header."""
    _add_block(project, tmp_path)
    invoke(project.root, "rm", "--group", "basic", "MyFilter", "-y")

    assert not (project.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_rm_removes_test_source(project: ProjectConfig, tmp_path: Path) -> None:
    """rm deletes qa_*.cpp alongside the header."""
    _add_block(project, tmp_path)
    invoke(project.root, "rm", "--group", "basic", "MyFilter", "-y")

    assert not (project.group_test_dir("basic") / "qa_MyFilter.cpp").exists()


def test_rm_removes_cmake_entry(project: ProjectConfig, tmp_path: Path) -> None:
    """rm removes the block from CMakeLists.txt."""
    _add_block(project, tmp_path)
    invoke(project.root, "rm", "--group", "basic", "MyFilter", "-y")

    cmake = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "MyFilter" not in cmake


def test_rm_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check is clean after rm (no stale entries or orphans)."""
    _add_block(project, tmp_path)
    invoke(project.root, "rm", "--group", "basic", "MyFilter", "-y")

    result = invoke(project.root, "check", "--json")
    data = json.loads(result.output)
    myfilter_issues = [i for i in data["issues"] if i["block"] == "MyFilter"]
    assert not myfilter_issues


# ---------------------------------------------------------------------------
# cp
# ---------------------------------------------------------------------------


def test_cp_produces_two_headers(project: ProjectConfig, tmp_path: Path) -> None:
    """cp leaves both the source and destination headers present."""
    _add_block(project, tmp_path)
    invoke(
        project.root,
        "cp",
        "--from-group",
        "basic",
        "--to-group",
        "basic",
        "MyFilter",
        "Booster",
        "--gen-test",
        "-y",
    )

    assert (project.group_include_dir("basic") / "MyFilter.hpp").exists()
    assert (project.group_include_dir("basic") / "Booster.hpp").exists()


def test_cp_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check is clean after cp (both blocks fully registered)."""
    _add_block(project, tmp_path)
    invoke(
        project.root,
        "cp",
        "--from-group",
        "basic",
        "--to-group",
        "basic",
        "MyFilter",
        "Booster",
        "--gen-test",
        "-y",
    )

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_cp_dst_cmake_uses_correct_target(project: ProjectConfig, tmp_path: Path) -> None:
    """CMakeLists.txt after cp contains entries for both blocks."""
    _add_block(project, tmp_path)
    invoke(
        project.root,
        "cp",
        "--from-group",
        "basic",
        "--to-group",
        "basic",
        "MyFilter",
        "Booster",
        "--gen-test",
        "-y",
    )

    cmake = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "MyFilter" in cmake
    assert "Booster" in cmake


# ---------------------------------------------------------------------------
# mv (between groups)
# ---------------------------------------------------------------------------


def test_mv_moves_header_to_destination_group(
    project_two_groups: ProjectConfig, tmp_path: Path
) -> None:
    """mv moves the block header from source group to destination group."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project_two_groups.root, "newblock", "--spec", str(spec))

    invoke(project_two_groups.root, "mv", "MyFilter", "--from", "basic", "--to", "filter", "-y")

    assert (project_two_groups.group_include_dir("filter") / "MyFilter.hpp").exists()
    assert not (project_two_groups.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_mv_check_clean_after_move(project_two_groups: ProjectConfig, tmp_path: Path) -> None:
    """check has no errors for either group after mv."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project_two_groups.root, "newblock", "--spec", str(spec))
    invoke(project_two_groups.root, "mv", "MyFilter", "--from", "basic", "--to", "filter", "-y")

    result = invoke(project_two_groups.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# rename-group
# ---------------------------------------------------------------------------


def test_rename_group_moves_directory(project_two_groups: ProjectConfig, tmp_path: Path) -> None:
    """rename-group renames the group directory on disk."""
    invoke(project_two_groups.root, "rename-group", "basic", "dsp", "-y")

    assert (project_two_groups.root / "blocks" / "dsp").exists()
    assert not (project_two_groups.root / "blocks" / "basic").exists()


def test_rename_group_info_json_reflects_new_name(
    project_two_groups: ProjectConfig, tmp_path: Path
) -> None:
    """info --json reports the new group name after rename-group."""
    invoke(project_two_groups.root, "rename-group", "basic", "dsp", "-y")

    result = invoke(project_two_groups.root, "info", "--json")
    names = [g["name"] for g in json.loads(result.output)["groups"]]
    assert "dsp" in names
    assert "basic" not in names


# ---------------------------------------------------------------------------
# Chained mutation: newblock → rename → cp → rm
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# rename-block alias (separate implementation in rename_block.py)
# ---------------------------------------------------------------------------


def test_rename_block_cmd_moves_header(project: ProjectConfig, tmp_path: Path) -> None:
    """rename-block alias renames the header file (separate from the rename command)."""
    _add_block(project, tmp_path)
    invoke(project.root, "rename-block", "--group", "basic", "MyFilter", "Booster", "-y")

    assert (project.group_include_dir("basic") / "Booster.hpp").exists()
    assert not (project.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_rename_block_cmd_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check passes after rename-block."""
    _add_block(project, tmp_path)
    invoke(project.root, "rename-block", "--group", "basic", "MyFilter", "Booster", "-y")

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_rename_block_cmd_invalid_name_exits_nonzero(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """rename-block exits nonzero when the new name is not CamelCase."""
    _add_block(project, tmp_path)
    result = invoke(
        project.root,
        "rename-block",
        "--group",
        "basic",
        "MyFilter",
        "booster",
        "-y",
        expect_ok=False,
    )
    assert result.exit_code != 0


def test_rename_group_updates_config(project_two_groups: ProjectConfig, tmp_path: Path) -> None:
    """rename-group updates .gr4modtool.toml so the new group key appears."""
    from gr4_modtool.project.discovery import load_config

    invoke(project_two_groups.root, "rename-group", "basic", "dsp", "-y")

    cfg = load_config(project_two_groups.root)
    assert "dsp" in cfg.groups
    assert "basic" not in cfg.groups


def test_rename_group_invalid_name_errors(
    project_two_groups: ProjectConfig, tmp_path: Path
) -> None:
    """rename-group rejects a new name that is not a valid identifier."""
    result = invoke(
        project_two_groups.root, "rename-group", "basic", "My-Group", "-y", expect_ok=False
    )
    assert result.exit_code != 0


def test_rename_group_nonexistent_group_errors(
    project_two_groups: ProjectConfig, tmp_path: Path
) -> None:
    """rename-group exits nonzero when the source group does not exist."""
    result = invoke(
        project_two_groups.root, "rename-group", "ghost", "newname", "-y", expect_ok=False
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# cp — cross-group
# ---------------------------------------------------------------------------


def test_cp_cross_group_header_in_dest(project_two_groups: ProjectConfig, tmp_path: Path) -> None:
    """cp --to-group places the copied header in the destination group."""
    cfg = project_two_groups
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(cfg.root, "newblock", "--spec", str(spec))

    invoke(
        cfg.root,
        "cp",
        "--from-group",
        "basic",
        "--to-group",
        "filter",
        "MyFilter",
        "MyFilter",
        "-y",
    )

    assert (cfg.group_include_dir("filter") / "MyFilter.hpp").exists()
    assert (cfg.group_include_dir("basic") / "MyFilter.hpp").exists()


def test_cp_cross_group_check_clean(project_two_groups: ProjectConfig, tmp_path: Path) -> None:
    """check is clean after cross-group cp (both copies fully registered)."""
    cfg = project_two_groups
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(cfg.root, "newblock", "--spec", str(spec))

    invoke(
        cfg.root,
        "cp",
        "--from-group",
        "basic",
        "--to-group",
        "filter",
        "MyFilter",
        "MyFilter",
        "--gen-test",
        "-y",
    )

    result = invoke(cfg.root, "check", "--json")
    import json

    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# Chained mutation
# ---------------------------------------------------------------------------


def test_full_mutation_chain_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """A create → rename → copy → remove sequence leaves the project clean."""
    _add_block(project, tmp_path, "Alpha")

    invoke(project.root, "rename", "--group", "basic", "Alpha", "Beta", "-y")
    invoke(
        project.root,
        "cp",
        "--from-group",
        "basic",
        "--to-group",
        "basic",
        "Beta",
        "Gamma",
        "--gen-test",
        "-y",
    )
    invoke(project.root, "rm", "--group", "basic", "Beta", "-y")

    result = invoke(project.root, "check", "--json")
    data = json.loads(result.output)
    # Alpha and Beta are gone; Gamma should be the only block and it should be clean
    remaining_errors = [
        i for i in data["issues"] if i["block"] in ("Alpha", "Beta") and i["severity"] == "error"
    ]
    assert not remaining_errors
    assert (project.group_include_dir("basic") / "Gamma.hpp").exists()
