"""E2E: flat-project command sequences (no groups)."""

from __future__ import annotations

import json
from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec


def _flat_spec(tmp_path: Path, block_name: str = "MyFilter") -> Path:
    return write_spec(tmp_path / "spec.yaml", block_name, group="", archetype="sync")


# ---------------------------------------------------------------------------
# newblock → check
# ---------------------------------------------------------------------------


def test_flat_newblock_then_check_clean(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """After newblock the flat project passes check with no errors."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    result = invoke(project_flat.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_flat_newblock_header_at_flat_path(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """Header lands in blocks/include/<prefix>/ not a group subdirectory."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    header = project_flat.block_include_dir() / "MyFilter.hpp"
    assert header.exists()
    # Must NOT be under a named group subdirectory
    assert "basic" not in str(header.parent)


def test_flat_newblock_test_at_flat_path(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """Test source lands in blocks/test/ not a group subdirectory."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    test = project_flat.block_test_dir() / "qa_MyFilter.cpp"
    assert test.exists()


def test_flat_newblock_cmake_uses_blocks_headers_target(
    project_flat: ProjectConfig, tmp_path: Path
) -> None:
    """CMakeLists.txt uses ::blocks_headers (no group suffix) in flat mode."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    cmake = (project_flat.block_test_dir() / "CMakeLists.txt").read_text()
    assert "blocks_headers" in cmake
    assert "blocks_basic_headers" not in cmake


def test_flat_newblock_namespace_has_no_group(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """Generated header uses project namespace without a group suffix."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    text = (project_flat.block_include_dir() / "MyFilter.hpp").read_text()
    assert "gr::testmod" in text
    assert "gr::testmod::basic" not in text


# ---------------------------------------------------------------------------
# info in flat mode
# ---------------------------------------------------------------------------


def test_flat_info_json_group_name_empty(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """info --json has groups[0].name == '' in flat mode."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    result = invoke(project_flat.root, "info", "--json")
    data = json.loads(result.output)
    assert data["groups"][0]["name"] == ""


def test_flat_info_table_no_group_column(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """info table suppresses the Group column in flat mode."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    result = invoke(project_flat.root, "info")
    assert "Group" not in result.output


# ---------------------------------------------------------------------------
# check → sync cycle in flat mode
# ---------------------------------------------------------------------------


def test_flat_sync_generates_missing_test(project_flat: ProjectConfig) -> None:
    """sync --yes creates a qa_*.cpp stub for a header that has no test."""
    (project_flat.block_include_dir() / "Orphan.hpp").write_text(
        "#pragma once\n"
        "#include <gnuradio-4.0/Block.hpp>\n"
        "namespace gr::testmod {\n"
        "template <typename T>\n"
        "struct Orphan : Block<Orphan<T>> {};\n"
        "} // namespace gr::testmod\n"
        "GR_REGISTER_BLOCK(Orphan, gr::testmod, Orphan, [float])\n"
    )

    result = invoke(project_flat.root, "check", "--json")
    data = json.loads(result.output)
    assert any(i["block"] == "Orphan" for i in data["issues"])

    invoke(project_flat.root, "sync", "--yes")

    assert (project_flat.block_test_dir() / "qa_Orphan.cpp").exists()
    result = invoke(project_flat.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_flat_newgroup_errors(project_flat: ProjectConfig) -> None:
    """newgroup exits non-zero in a flat project."""
    result = invoke(project_flat.root, "newgroup", "--name", "extra", expect_ok=False)
    assert result.exit_code != 0


def test_flat_mv_errors(project_flat: ProjectConfig) -> None:
    """mv exits non-zero in a flat project."""
    result = invoke(project_flat.root, "mv", "--from", "a", "--to", "b", "-y", expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# rename in flat mode
# ---------------------------------------------------------------------------


def test_flat_rename_check_clean(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """rename works in flat mode and leaves the project clean."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    invoke(project_flat.root, "rename", "MyFilter", "FlatBooster", "-y")

    assert (project_flat.block_include_dir() / "FlatBooster.hpp").exists()
    assert not (project_flat.block_include_dir() / "MyFilter.hpp").exists()

    result = invoke(project_flat.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# export-spec in flat mode
# ---------------------------------------------------------------------------


def test_flat_export_spec_creates_yaml(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """export-spec produces at least one YAML file from a flat project."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    out_dir = project_flat.root / "specs"
    invoke(project_flat.root, "export-spec", "--out-dir", str(out_dir))

    yaml_files = list(out_dir.glob("*.yaml"))
    assert yaml_files, "export-spec wrote no YAML files for flat project"


# ---------------------------------------------------------------------------
# lint-headers in flat mode
# ---------------------------------------------------------------------------


def test_flat_lint_headers_exits_ok(project_flat: ProjectConfig, tmp_path: Path) -> None:
    """lint-headers exits 0 on a valid flat-layout block."""
    spec = _flat_spec(tmp_path)
    invoke(project_flat.root, "newblock", "--spec", str(spec))

    invoke(project_flat.root, "lint-headers")
