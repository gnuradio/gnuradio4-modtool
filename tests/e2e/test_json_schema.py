"""E2E: JSON output schema consistency.

Verifies that commands producing --json output emit stable, well-structured
responses across different project states.
"""

from __future__ import annotations

import json
from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec

# ---------------------------------------------------------------------------
# info --json
# ---------------------------------------------------------------------------


def test_info_json_top_level_keys(project: ProjectConfig) -> None:
    """info --json has name, version, cpp_namespace, build_cmake, groups."""
    result = invoke(project.root, "info", "--json")
    data = json.loads(result.output)
    for key in ("name", "version", "cpp_namespace", "build_cmake", "groups"):
        assert key in data, f"missing key: {key}"


def test_info_json_group_has_name_and_blocks(project: ProjectConfig) -> None:
    """Each group entry in info --json has name and blocks list."""
    result = invoke(project.root, "info", "--json")
    data = json.loads(result.output)
    for group in data["groups"]:
        assert "name" in group
        assert "blocks" in group
        assert isinstance(group["blocks"], list)


def test_info_json_block_has_name(project: ProjectConfig, tmp_path: Path) -> None:
    """Each block entry in info --json has at least a name field."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "info", "--json")
    data = json.loads(result.output)
    group_data = next(g for g in data["groups"] if g["name"] == "basic")
    for block in group_data["blocks"]:
        assert "name" in block


def test_info_verbose_json_block_has_ports(project: ProjectConfig, tmp_path: Path) -> None:
    """info --verbose --json adds a ports key to each block entry."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "info", "--json", "--verbose")
    data = json.loads(result.output)
    group_data = next(g for g in data["groups"] if g["name"] == "basic")
    block = next(b for b in group_data["blocks"] if b["name"] == "MyFilter")
    assert "ports" in block
    assert "in" in block["ports"]
    assert "out" in block["ports"]


def test_info_verbose_json_block_has_params(project: ProjectConfig, tmp_path: Path) -> None:
    """info --verbose --json adds a params key to each block entry."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "info", "--json", "--verbose")
    data = json.loads(result.output)
    group_data = next(g for g in data["groups"] if g["name"] == "basic")
    block = next(b for b in group_data["blocks"] if b["name"] == "MyFilter")
    assert "params" in block
    assert isinstance(block["params"], list)


# ---------------------------------------------------------------------------
# check --json
# ---------------------------------------------------------------------------


def test_check_json_top_level_keys(project: ProjectConfig) -> None:
    """check --json has issues, error_count, and warning_count."""
    result = invoke(project.root, "check", "--json")
    data = json.loads(result.output)
    for key in ("issues", "error_count", "warning_count"):
        assert key in data, f"missing key: {key}"


def test_check_json_issue_has_fields(project: ProjectConfig, tmp_path: Path) -> None:
    """Each issue entry in check --json has group, block, issue, severity."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    # Break cmake entry to force an issue
    cmake = project.group_test_dir("basic") / "CMakeLists.txt"
    cmake.write_text(
        "\n".join(line for line in cmake.read_text().splitlines() if "MyFilter" not in line) + "\n"
    )

    result = invoke(project.root, "check", "--json", expect_ok=False)
    data = json.loads(result.output)
    assert data["error_count"] > 0
    for issue in data["issues"]:
        for field in ("group", "block", "issue", "severity"):
            assert field in issue, f"issue missing field: {field}"


def test_check_json_counts_match_issues(project: ProjectConfig, tmp_path: Path) -> None:
    """error_count and warning_count in check --json match the actual issue lists."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "check", "--json")
    data = json.loads(result.output)
    errors = sum(1 for i in data["issues"] if i["severity"] == "error")
    warnings = sum(1 for i in data["issues"] if i["severity"] == "warning")
    assert data["error_count"] == errors
    assert data["warning_count"] == warnings


# ---------------------------------------------------------------------------
# lint-headers --json
# ---------------------------------------------------------------------------


def test_lint_headers_json_schema(project: ProjectConfig, tmp_path: Path) -> None:
    """lint-headers --json has error_count and a list of issues."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "lint-headers", "--json")
    data = json.loads(result.output)
    assert "error_count" in data
    assert isinstance(data["error_count"], int)
