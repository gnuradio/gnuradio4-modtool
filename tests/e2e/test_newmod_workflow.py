"""E2E: newmod command workflow.

Tests the newmod --yes flag (non-interactive mode) which accepts all
questionary prompts at their defaults.  Verifies that the generated project
structure is correct and that subsequent commands work against it.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gr4_modtool.cli import cli
from gr4_modtool.project.discovery import load_config

from .conftest import invoke


def _newmod(dest: Path, name: str, *extra_args: str) -> Path:
    """Run newmod --yes and return the created project root."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["newmod", "--project-dir", str(dest), "--name", name, "--yes", *extra_args]
    )
    assert result.exit_code == 0, f"newmod failed:\n{result.output}"
    return dest / name


# ---------------------------------------------------------------------------
# Basic scaffold
# ---------------------------------------------------------------------------


def test_newmod_creates_config(tmp_path: Path) -> None:
    """newmod --yes creates .gr4modtool.toml with correct name and version."""
    root = _newmod(tmp_path, "mymod")

    cfg = load_config(root)
    assert cfg.name == "mymod"
    assert cfg.version == "0.1.0"


def test_newmod_gr4_prefixed_name_strips_prefix_from_namespace(tmp_path: Path) -> None:
    """A gr4_-prefixed project name does not leak the prefix into the C++ namespace."""
    root = _newmod(tmp_path, "gr4_josh")

    cfg = load_config(root)
    assert cfg.cpp_namespace == "gr::josh"
    assert cfg.cmake_prefix == "gr4_josh"


def test_newmod_plain_name_namespace(tmp_path: Path) -> None:
    """An unprefixed project name maps directly to gr::<name> / gr4_<name>."""
    root = _newmod(tmp_path, "mymod")

    cfg = load_config(root)
    assert cfg.cpp_namespace == "gr::mymod"
    assert cfg.cmake_prefix == "gr4_mymod"


def test_newmod_cmake_scaffold(tmp_path: Path) -> None:
    """newmod --yes generates CMakeLists.txt and cmake/Dependencies.cmake."""
    root = _newmod(tmp_path, "mymod")

    assert (root / "CMakeLists.txt").exists()
    assert (root / "cmake" / "Dependencies.cmake").exists()


def test_newmod_flat_by_default(tmp_path: Path) -> None:
    """newmod --yes creates a flat project with no groups by default."""
    root = _newmod(tmp_path, "mymod")

    cfg = load_config(root)
    assert cfg.flat is True
    assert cfg.groups == {}


def test_newmod_first_group_flag(tmp_path: Path) -> None:
    """--first-group creates a grouped project with the named group."""
    root = _newmod(tmp_path, "mymod", "--first-group", "basic")

    cfg = load_config(root)
    assert "basic" in cfg.groups
    assert cfg.flat is False


def test_newmod_project_dir_flag(tmp_path: Path) -> None:
    """--project-dir places the project inside the specified directory."""
    dest = tmp_path / "projects"
    dest.mkdir()
    root = _newmod(dest, "mymod")

    assert root == dest / "mymod"
    assert root.is_dir()


# ---------------------------------------------------------------------------
# newmod → newblock → check
# ---------------------------------------------------------------------------


def test_newmod_then_newblock_check_clean(tmp_path: Path) -> None:
    """Full from-scratch flow: newmod → newblock → check exits 0."""
    root = _newmod(tmp_path, "mymod")

    spec = tmp_path / "spec.yaml"
    spec.write_text(
        'block_name: MyFilter\ngroup: basic\narchetype: sync\ntype_list: "float"\ngen_test: true\n'
    )
    invoke(root, "newblock", "--spec", str(spec))

    result = invoke(root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_newmod_then_newgroup_then_newblock_check_clean(tmp_path: Path) -> None:
    """newmod → newgroup → newblock → check: multi-group project stays clean."""
    root = _newmod(tmp_path, "mymod", "--first-group", "basic")

    invoke(root, "newgroup", "--name", "dsp")

    spec = tmp_path / "spec.yaml"
    spec.write_text(
        'block_name: LowPass\ngroup: dsp\narchetype: sync\ntype_list: "float"\ngen_test: true\n'
    )
    invoke(root, "newblock", "--spec", str(spec))

    result = invoke(root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# Default-True optional files (gen_clang=True, gen_vscode=True in --yes mode)
# ---------------------------------------------------------------------------


def test_newmod_yes_creates_clang_format(tmp_path: Path) -> None:
    """newmod --yes generates .clang-format (its questionary default is True)."""
    root = _newmod(tmp_path, "mymod")
    assert (root / ".clang-format").exists()


def test_newmod_yes_creates_vscode_settings(tmp_path: Path) -> None:
    """newmod --yes generates .vscode/settings.json (its questionary default is True)."""
    root = _newmod(tmp_path, "mymod")
    assert (root / ".vscode" / "settings.json").exists()
