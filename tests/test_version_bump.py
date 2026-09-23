"""Tests for gr4_modtool version-bump command."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from gr4_modtool.commands.version_bump import (
    _bump_version,
    _parse_semver,
    _update_cmake,
    _update_doxyfile,
    apply_version_bump,
    cmd,
)
from gr4_modtool.project.discovery import load_config

# ---------------------------------------------------------------------------
# _parse_semver
# ---------------------------------------------------------------------------


def test_parse_semver_valid() -> None:
    assert _parse_semver("1.2.3") == (1, 2, 3)
    assert _parse_semver("0.0.0") == (0, 0, 0)
    assert _parse_semver("10.20.30") == (10, 20, 30)


@pytest.mark.parametrize("bad", ["1.2", "abc", "1.2.3.4", "", "v1.2.3", "1.2.x"])
def test_parse_semver_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        _parse_semver(bad)


# ---------------------------------------------------------------------------
# _bump_version
# ---------------------------------------------------------------------------


def test_bump_major() -> None:
    assert _bump_version("1.2.3", "major") == "2.0.0"


def test_bump_minor() -> None:
    assert _bump_version("1.2.3", "minor") == "1.3.0"


def test_bump_patch() -> None:
    assert _bump_version("1.2.3", "patch") == "1.2.4"


def test_bump_patch_zero_start() -> None:
    assert _bump_version("0.1.0", "patch") == "0.1.1"


# ---------------------------------------------------------------------------
# _update_cmake
# ---------------------------------------------------------------------------


def test_update_cmake_found(tmp_path) -> None:
    f = tmp_path / "CMakeLists.txt"
    f.write_text("project(mymod LANGUAGES CXX VERSION 1.2.3)\n")
    assert _update_cmake(f, "1.2.3", "2.0.0") is True
    assert "VERSION 2.0.0" in f.read_text()
    assert "1.2.3" not in f.read_text()


def test_update_cmake_missing_file(tmp_path) -> None:
    assert _update_cmake(tmp_path / "CMakeLists.txt", "1.2.3", "2.0.0") is False


def test_update_cmake_not_matched(tmp_path) -> None:
    f = tmp_path / "CMakeLists.txt"
    f.write_text("cmake_minimum_required(VERSION 3.22)\n")
    assert _update_cmake(f, "1.2.3", "2.0.0") is False
    assert f.read_text() == "cmake_minimum_required(VERSION 3.22)\n"


# ---------------------------------------------------------------------------
# _update_doxyfile
# ---------------------------------------------------------------------------


def test_update_doxyfile_found(tmp_path) -> None:
    f = tmp_path / "Doxyfile"
    f.write_text('PROJECT_NUMBER         = "1.2.3"\n')
    assert _update_doxyfile(f, "1.2.3", "1.2.4") is True
    assert '"1.2.4"' in f.read_text()


def test_update_doxyfile_missing_file(tmp_path) -> None:
    assert _update_doxyfile(tmp_path / "Doxyfile", "1.2.3", "1.2.4") is False


# ---------------------------------------------------------------------------
# apply_version_bump
# ---------------------------------------------------------------------------


def test_apply_updates_config(project) -> None:
    apply_version_bump(project, "1.0.0")
    reloaded = load_config(project.root)
    assert reloaded.version == "1.0.0"


def test_apply_updates_cmake(project) -> None:
    cmake = project.root / "CMakeLists.txt"
    cmake.write_text(f"project(testmod LANGUAGES CXX VERSION {project.version})\n")

    modified = apply_version_bump(project, "2.0.0")

    assert cmake in modified
    assert "VERSION 2.0.0" in cmake.read_text()


def test_apply_skips_absent_files(project) -> None:
    """Only .gr4modtool.toml in modified list when no build files exist at root."""
    modified = apply_version_bump(project, "9.9.9")
    names = {p.name for p in modified}
    assert names == {".gr4modtool.toml"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_cli_patch_yes(runner, project) -> None:
    result = runner.invoke(cmd, ["--patch", "--yes", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert load_config(project.root).version == "0.1.1"


def test_cli_minor_yes(runner, project) -> None:
    result = runner.invoke(cmd, ["--minor", "--yes", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert load_config(project.root).version == "0.2.0"


def test_cli_major_yes(runner, project) -> None:
    result = runner.invoke(cmd, ["--major", "--yes", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert load_config(project.root).version == "1.0.0"


def test_cli_set_yes(runner, project) -> None:
    result = runner.invoke(cmd, ["--set", "3.0.0", "--yes", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert load_config(project.root).version == "3.0.0"


def test_cli_set_invalid_format(runner, project) -> None:
    result = runner.invoke(
        cmd, ["--set", "notaversion", "--yes", "--project-dir", str(project.root)]
    )
    assert result.exit_code != 0


def test_cli_conflicting_options(runner, project) -> None:
    result = runner.invoke(
        cmd, ["--patch", "--set", "1.0.0", "--yes", "--project-dir", str(project.root)]
    )
    assert result.exit_code != 0


def test_cli_dry_run(runner, project) -> None:
    original = project.version
    result = runner.invoke(cmd, ["--patch", "--dry-run", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert load_config(project.root).version == original


def test_cli_shows_transition(runner, project) -> None:
    result = runner.invoke(cmd, ["--patch", "--yes", "--project-dir", str(project.root)])
    assert "0.1.0" in result.output
    assert "0.1.1" in result.output


def test_cli_dry_run_shows_files(runner, project) -> None:
    cmake = project.root / "CMakeLists.txt"
    cmake.write_text(f"project(testmod LANGUAGES CXX VERSION {project.version})\n")
    result = runner.invoke(cmd, ["--patch", "--dry-run", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert "CMakeLists.txt" in result.output
    assert cmake.read_text() == f"project(testmod LANGUAGES CXX VERSION {project.version})\n"


def test_cli_patch_updates_doxyfile(runner, project) -> None:
    doxy = project.root / "Doxyfile"
    doxy.write_text(f'PROJECT_NUMBER         = "{project.version}"\n')
    result = runner.invoke(cmd, ["--patch", "--yes", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert '"0.1.1"' in doxy.read_text()


def test_cli_dry_run_shows_doxyfile(runner, project) -> None:
    doxy = project.root / "Doxyfile"
    original = f'PROJECT_NUMBER         = "{project.version}"\n'
    doxy.write_text(original)
    result = runner.invoke(cmd, ["--patch", "--dry-run", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert "Doxyfile" in result.output
    assert doxy.read_text() == original
