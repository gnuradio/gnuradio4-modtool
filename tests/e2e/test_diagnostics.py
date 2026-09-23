"""E2E: show and doctor command workflows.

Tests the diagnostic commands that inspect the project or environment:
  - show     (display a block's header or test file)
  - doctor   (check environment readiness)
"""

from __future__ import annotations

import json
from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec

# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


def test_show_displays_header(project: ProjectConfig, tmp_path: Path) -> None:
    """show <block> exits 0 and prints header content."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "show", "MyFilter", "--group", "basic")
    assert "MyFilter" in result.output


def test_show_displays_test_file(project: ProjectConfig, tmp_path: Path) -> None:
    """show <block> --test exits 0 and prints test file content."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "show", "MyFilter", "--group", "basic", "--test")
    assert "MyFilter" in result.output


def test_show_missing_block_errors(project: ProjectConfig) -> None:
    """show exits nonzero when the requested block does not exist."""
    result = invoke(project.root, "show", "NonExistent", "--group", "basic", expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def test_doctor_runs(project: ProjectConfig) -> None:
    """doctor runs without unhandled exceptions (exit code reflects environment)."""
    # Exit code 1 is acceptable when the environment is missing tools (e.g. cmake).
    invoke(project.root, "doctor", expect_ok=False)


def test_doctor_json_is_list(project: ProjectConfig) -> None:
    """doctor --json emits a JSON array regardless of environment health."""
    result = invoke(project.root, "doctor", "--json", expect_ok=False)
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0


def test_doctor_json_has_python_check(project: ProjectConfig) -> None:
    """doctor --json always includes a python check entry."""
    result = invoke(project.root, "doctor", "--json", expect_ok=False)
    data = json.loads(result.output)
    names = [item["name"] for item in data]
    assert "python" in names


def test_doctor_json_check_fields(project: ProjectConfig) -> None:
    """Every item in doctor --json output has name, status, and detail fields."""
    result = invoke(project.root, "doctor", "--json", expect_ok=False)
    data = json.loads(result.output)
    for item in data:
        assert "name" in item
        assert "status" in item
        assert "detail" in item
