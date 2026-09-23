"""coverage command — build with coverage flags, run tests, generate HTML report."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

import click

from gr4_modtool.commands.build import run_build
from gr4_modtool.log import get_logger, log_exit, log_run
from gr4_modtool.project.discovery import find_project_root

log = get_logger(__name__)


def _detect_tool(preferred: str) -> str | None:
    """Return the coverage tool to use, or None if nothing is available."""
    if preferred == "auto":
        for tool in ("gcovr", "llvm-cov"):
            if shutil.which(tool):
                return tool
        return None
    return preferred if shutil.which(preferred) else None


def detect_coverage_tool(preferred: str = "auto") -> str | None:
    """Public wrapper around _detect_tool for use by other commands."""
    return _detect_tool(preferred)


def _coverage_flags(tool: str, output_dir: Path) -> tuple[list[str], dict[str, str]]:
    """Return (cmake_args, test_env) for the given coverage tool."""
    base = ["-DCMAKE_BUILD_TYPE=Debug", "-DENABLE_TESTING=ON"]
    if tool == "gcovr":
        return (
            base + ["-DCMAKE_CXX_FLAGS=--coverage", "-DCMAKE_EXE_LINKER_FLAGS=--coverage"],
            {},
        )
    # llvm-cov
    return (
        base
        + [
            "-DCMAKE_CXX_FLAGS=-fprofile-instr-generate -fcoverage-mapping",
            "-DCMAKE_EXE_LINKER_FLAGS=-fprofile-instr-generate",
        ],
        {"LLVM_PROFILE_FILE": str(output_dir / "default-%p.profraw")},
    )


def coverage_test_env(tool: str, output_dir: Path) -> dict[str, str]:
    """Return extra env vars to pass when running tests for coverage collection.

    For llvm-cov: sets LLVM_PROFILE_FILE so profraw data lands in output_dir.
    For gcovr: returns {} since gcno/gcda files are written automatically.
    """
    if tool == "llvm-cov":
        return {"LLVM_PROFILE_FILE": str(output_dir / "default-%p.profraw")}
    return {}


def _run_tests(project_root: Path, build_dir: Path, env: dict[str, str] | None = None) -> int:
    """Run all tests, merging optional env vars for coverage profiling."""
    cmd = ["ctest", "--test-dir", str(build_dir), "--output-on-failure"]
    click.echo(f"  $ {' '.join(cmd)}")
    log_run(log, cmd, project_root)
    merged = {**os.environ, **(env or {})}
    proc = subprocess.Popen(cmd, env=merged, stdout=sys.stdout, stderr=sys.stderr)
    rc = proc.wait()
    log_exit(log, cmd, rc)
    return rc


def _run(cmd: list[str]) -> int:
    click.echo(f"  $ {' '.join(cmd)}")
    log_run(log, cmd)
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    rc = proc.wait()
    log_exit(log, cmd, rc)
    return rc


def _run_gcovr(project_root: Path, build_dir: Path, output_dir: Path) -> int:
    return _run(
        [
            "gcovr",
            "--root",
            str(project_root),
            "--build-dir",
            str(build_dir),
            "--exclude-directories",
            str(build_dir / "CMakeFiles"),
            "--html-details",
            str(output_dir / "index.html"),
        ]
    )


def _run_llvm_cov(project_root: Path, build_dir: Path, output_dir: Path) -> int:
    profraw_files = list(output_dir.glob("*.profraw")) + list(build_dir.rglob("*.profraw"))
    if not profraw_files:
        click.echo(
            "No .profraw files found — did the tests run with LLVM_PROFILE_FILE set?",
            err=True,
        )
        return 1

    profdata = output_dir / "merged.profdata"
    rc = _run(
        ["llvm-profdata", "merge", "-sparse", *[str(f) for f in profraw_files], "-o", str(profdata)]
    )
    if rc != 0:
        return rc

    binaries = [f for f in build_dir.rglob("qa_*") if f.is_file() and os.access(f, os.X_OK)]
    if not binaries:
        click.echo("No qa_* test binaries found in build directory.", err=True)
        return 1

    return _run(
        [
            "llvm-cov",
            "show",
            str(binaries[0]),
            *[f"-object={b}" for b in binaries[1:]],
            f"-instr-profile={profdata}",
            "-format=html",
            f"-output-dir={output_dir}",
        ]
    )


def regenerate_coverage_report(
    project_root: Path,
    build_dir: Path,
    tool: str,
    output_dir: Path,
) -> int:
    """Re-generate the HTML report from existing build artefacts.

    Does not reconfigure, rebuild, or run tests — only runs the report tool.
    Intended for the watch loop where tests have just been run.
    """
    actual_tool = _detect_tool(tool)
    if actual_tool is None:
        click.echo(
            "No coverage tool found. Install gcovr (pip install gcovr) or llvm-cov.",
            err=True,
        )
        return 1
    output_dir.mkdir(parents=True, exist_ok=True)
    if actual_tool == "gcovr":
        return _run_gcovr(project_root, build_dir, output_dir)
    return _run_llvm_cov(project_root, build_dir, output_dir)


def run_coverage(
    project_root: Path,
    build_dir: Path,
    *,
    tool: str = "auto",
    output_dir: Path | None = None,
    open_browser: bool = True,
    jobs: int | None = None,
) -> int:
    """Configure, build, test, and report coverage. Returns test exit code."""
    actual_tool = _detect_tool(tool)
    if actual_tool is None:
        click.echo(
            "No coverage tool found. Install gcovr (pip install gcovr) or llvm-cov.",
            err=True,
        )
        return 1

    output_dir = output_dir or project_root / "coverage"
    output_dir.mkdir(parents=True, exist_ok=True)

    cmake_args, test_env = _coverage_flags(actual_tool, output_dir)

    rc = run_build(
        project_root,
        build_dir,
        reconfigure=True,
        run_tests=False,
        jobs=jobs,
        cmake_args=tuple(cmake_args),
    )
    if rc != 0:
        return rc

    rc_test = _run_tests(project_root, build_dir, env=test_env or None)
    if rc_test != 0:
        click.echo("Warning: some tests failed — coverage report may be incomplete.")

    if actual_tool == "gcovr":
        rc_report = _run_gcovr(project_root, build_dir, output_dir)
    else:
        rc_report = _run_llvm_cov(project_root, build_dir, output_dir)

    if rc_report != 0:
        return rc_report

    html = output_dir / "index.html"
    click.echo(f"\nCoverage report: {html}")
    if open_browser and html.exists():
        webbrowser.open(html.as_uri())

    return rc_test


@click.command("coverage")
@click.option(
    "--build-dir",
    default="build-coverage",
    show_default=True,
    help="Build directory for coverage-instrumented build.",
)
@click.option(
    "--output-dir", default="coverage", show_default=True, help="Directory for the HTML report."
)
@click.option(
    "--tool",
    type=click.Choice(["auto", "gcovr", "llvm-cov"]),
    default="auto",
    show_default=True,
    help="Coverage report tool (auto tries gcovr first).",
)
@click.option(
    "--open/--no-open",
    "open_browser",
    default=True,
    help="Open the HTML report in the default browser.",
)
@click.option("--jobs", "-j", default=None, type=int, help="Parallel build jobs.")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    build_dir: str,
    output_dir: str,
    tool: str,
    open_browser: bool,
    jobs: int | None,
    project_dir: str | None,
) -> None:
    """Build with coverage flags, run tests, and generate an HTML report."""
    if project_dir:
        root = Path(project_dir).resolve()
    else:
        root = find_project_root() or Path.cwd()

    bd = Path(build_dir) if Path(build_dir).is_absolute() else root / build_dir
    od = Path(output_dir) if Path(output_dir).is_absolute() else root / output_dir

    rc = run_coverage(root, bd, tool=tool, output_dir=od, open_browser=open_browser, jobs=jobs)
    if rc != 0:
        sys.exit(rc)
