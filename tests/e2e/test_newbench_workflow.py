"""E2E: newbench command workflow.

Tests the benchmark scaffolding command against an existing block.
  - newbench creates bench_*.cpp
  - newbench --wire-build wires into cmake
  - newbench --plot creates plot_*.py
  - newbench errors when header is missing
  - newbench errors when benchmark already exists
"""

from __future__ import annotations

from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec


def _make_block(project: ProjectConfig, tmp_path: Path, name: str = "MyFilter") -> None:
    """Create a block using the CLI."""
    spec = write_spec(tmp_path / f"spec_{name}.yaml", name, group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))


# ---------------------------------------------------------------------------
# Basic creation
# ---------------------------------------------------------------------------


def test_newbench_creates_bench_file(project: ProjectConfig, tmp_path: Path) -> None:
    """newbench creates bench_<BlockName>.cpp in the benchmarks directory."""
    _make_block(project, tmp_path)

    invoke(project.root, "newbench", "MyFilter", "--group", "basic", "-y")

    bench = project.group_bench_dir("basic") / "bench_MyFilter.cpp"
    assert bench.exists()


def test_newbench_wire_build_creates_cmake(project: ProjectConfig, tmp_path: Path) -> None:
    """newbench --wire-build creates benchmarks/CMakeLists.txt."""
    _make_block(project, tmp_path)

    invoke(project.root, "newbench", "MyFilter", "--group", "basic", "--wire-build", "-y")

    bench_cmake = project.group_bench_dir("basic") / "CMakeLists.txt"
    assert bench_cmake.exists()


def test_newbench_wire_build_cmake_contains_block(project: ProjectConfig, tmp_path: Path) -> None:
    """newbench --wire-build adds the block name to benchmarks/CMakeLists.txt."""
    _make_block(project, tmp_path)

    invoke(project.root, "newbench", "MyFilter", "--group", "basic", "--wire-build", "-y")

    bench_cmake = (project.group_bench_dir("basic") / "CMakeLists.txt").read_text()
    assert "MyFilter" in bench_cmake


def test_newbench_plot_creates_script(project: ProjectConfig, tmp_path: Path) -> None:
    """newbench --plot generates plot_<BlockName>.py alongside the benchmark."""
    _make_block(project, tmp_path)

    invoke(project.root, "newbench", "MyFilter", "--group", "basic", "--plot", "-y")

    plot = project.group_bench_dir("basic") / "plot_MyFilter.py"
    assert plot.exists()


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_newbench_errors_on_missing_header(project: ProjectConfig) -> None:
    """newbench exits nonzero when the block header does not exist."""
    result = invoke(
        project.root,
        "newbench",
        "NonExistent",
        "--group",
        "basic",
        "-y",
        expect_ok=False,
    )
    assert result.exit_code != 0


def test_newbench_errors_on_duplicate(project: ProjectConfig, tmp_path: Path) -> None:
    """newbench exits nonzero when the benchmark already exists."""
    _make_block(project, tmp_path)

    invoke(project.root, "newbench", "MyFilter", "--group", "basic", "-y")
    result = invoke(
        project.root,
        "newbench",
        "MyFilter",
        "--group",
        "basic",
        "-y",
        expect_ok=False,
    )
    assert result.exit_code != 0
