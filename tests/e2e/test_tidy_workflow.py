"""E2E: tidy command — clang-tidy integration and config generation.

tidy --init is always testable (writes config files, no binary needed).
Run-mode tests mock shutil.which so they work regardless of whether
clang-tidy is installed on the host.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke

# ---------------------------------------------------------------------------
# --init mode (no clang-tidy binary required)
# ---------------------------------------------------------------------------


def test_tidy_init_creates_clang_format(project: ProjectConfig) -> None:
    """tidy --init writes a .clang-format file at the project root."""
    invoke(project.root, "tidy", "--init")
    assert (project.root / ".clang-format").exists()


def test_tidy_init_creates_clang_tidy_config(project: ProjectConfig) -> None:
    """tidy --init writes a .clang-tidy file at the project root."""
    invoke(project.root, "tidy", "--init")
    assert (project.root / ".clang-tidy").exists()


# ---------------------------------------------------------------------------
# Run mode — mocked binary presence so tests are environment-independent
# ---------------------------------------------------------------------------


def test_tidy_missing_binary_exits_ok(project: ProjectConfig) -> None:
    """tidy exits 0 with a warning when clang-tidy binary is not found."""
    with patch("gr4_modtool.commands.tidy.shutil.which", return_value=None):
        result = invoke(project.root, "tidy")
    assert result.exit_code == 0


def test_tidy_missing_compile_commands_exits_nonzero(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """tidy exits nonzero when compile_commands.json is absent from the build dir."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    with patch("gr4_modtool.commands.tidy.shutil.which", return_value="/usr/bin/clang-tidy"):
        result = invoke(
            project.root,
            "tidy",
            "--build-dir",
            str(build_dir),
            expect_ok=False,
        )
    assert result.exit_code != 0
