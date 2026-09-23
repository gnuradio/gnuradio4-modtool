"""doctor command — check that the environment has everything gr4_modtool needs."""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from gr4_modtool.log import format_command, get_logger
from gr4_modtool.project.discovery import load_config

log = get_logger(__name__)


_STATUS_STYLE = {
    "ok": "green",
    "warning": "yellow",
    "error": "red",
    "skip": "dim",
    "info": "dim",
}


@dataclass
class DoctorResult:
    name: str
    status: str  # "ok" | "warning" | "error" | "skip" | "info"
    detail: str


def _run_version(cmd: list[str]) -> str | None:
    """Run cmd, return first X.Y.Z (or X.Y) from combined output, or None on failure."""
    log.debug("probing version: %s", format_command(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", r.stdout + r.stderr)
        return m.group(1) if m else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        log.debug("%s unavailable: %s", cmd[0], exc)
        return None


def _parse_ver(v: str) -> tuple[int, ...]:
    """Convert 'X.Y.Z' to (X, Y, Z) for comparison."""
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_python() -> list[DoctorResult]:
    vi = sys.version_info
    ver = f"{vi.major}.{vi.minor}.{vi.micro}"
    if vi < (3, 11):
        return [DoctorResult("python", "error", f"Python {ver} (need ≥ 3.11)")]
    return [DoctorResult("python", "ok", f"Python {ver}")]


def _check_cmake(need_cmake: bool) -> list[DoctorResult]:
    if not need_cmake:
        return [DoctorResult("cmake", "skip", "not required by project")]
    if not shutil.which("cmake"):
        return [DoctorResult("cmake", "error", "not found — install cmake ≥ 3.22")]
    ver = _run_version(["cmake", "--version"])
    if ver and ver != "unknown" and _parse_ver(ver) < (3, 22):
        return [DoctorResult("cmake", "error", f"cmake {ver} (need ≥ 3.22)")]
    return [DoctorResult("cmake", "ok", f"cmake {ver}")]


def _check_pkg_config() -> DoctorResult:
    if not shutil.which("pkg-config"):
        return DoctorResult("pkg-config", "warning", "not found — required to detect gnuradio4")
    ver = _run_version(["pkg-config", "--version"])
    return DoctorResult("pkg-config", "ok", f"pkg-config {ver}")


def _check_cxx_compiler() -> list[DoctorResult]:
    for compiler in ("g++", "clang++"):
        if shutil.which(compiler):
            ver = _run_version([compiler, "--version"])
            return [DoctorResult("C++ compiler", "ok", f"{compiler} {ver}")]
    return [
        DoctorResult(
            "C++ compiler",
            "error",
            "neither g++ nor clang++ found — install a C++23-capable compiler",
        )
    ]


def _check_gnuradio4() -> DoctorResult:
    if not shutil.which("pkg-config"):
        return DoctorResult("gnuradio4", "skip", "pkg-config not found; cannot detect")
    try:
        r = subprocess.run(
            ["pkg-config", "--modversion", "gnuradio4"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return DoctorResult("gnuradio4", "skip", "pkg-config failed unexpectedly")
    if r.returncode != 0:
        return DoctorResult(
            "gnuradio4",
            "error",
            "not found via pkg-config — install GNURadio 4 and set PKG_CONFIG_PATH",
        )
    ver = r.stdout.strip()
    return DoctorResult("gnuradio4", "ok", f"gnuradio4 {ver}")


def _check_optional_tools() -> list[DoctorResult]:
    results: list[DoctorResult] = []

    for tool in ("clang-format", "clang-tidy", "git"):
        if shutil.which(tool):
            ver = _run_version([tool, "--version"])
            results.append(DoctorResult(tool, "info", f"{tool} {ver}"))
        else:
            results.append(DoctorResult(tool, "info", "not found (optional)"))

    # Coverage: at least one of gcovr or llvm-cov
    cov_tools = [t for t in ("gcovr", "llvm-cov") if shutil.which(t)]
    if cov_tools:
        versions = []
        for t in cov_tools:
            ver = _run_version([t, "--version"])
            versions.append(f"{t} {ver}")
        results.append(DoctorResult("coverage tool", "info", ", ".join(versions)))
    else:
        results.append(
            DoctorResult(
                "coverage tool",
                "info",
                "neither gcovr nor llvm-cov found (optional; pip install gcovr)",
            )
        )

    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_doctor(cfg=None) -> list[DoctorResult]:
    """Run all environment checks. cfg is used to scope build-system checks."""
    need_cmake = cfg.build_cmake if cfg is not None else True

    results: list[DoctorResult] = []
    results += _check_python()
    results += _check_cmake(need_cmake)
    results.append(_check_pkg_config())
    results += _check_cxx_compiler()
    results.append(_check_gnuradio4())
    results += _check_optional_tools()
    return results


def _print_results(cfg, results: list[DoctorResult]) -> None:
    console = Console()

    if cfg is not None:
        console.print(f"[bold]Project:[/bold] {cfg.name} at {cfg.root}")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    for r in results:
        style = _STATUS_STYLE.get(r.status, "white")
        table.add_row(r.name, f"[{style}]{r.status}[/{style}]", r.detail)

    console.print(table)

    n_ok = sum(1 for r in results if r.status == "ok")
    n_warn = sum(1 for r in results if r.status == "warning")
    n_err = sum(1 for r in results if r.status == "error")

    parts = [f"[green]{n_ok} passed[/green]"]
    if n_warn:
        parts.append(f"[yellow]{n_warn} warning(s)[/yellow]")
    if n_err:
        parts.append(f"[red]{n_err} error(s)[/red]")
    console.print("  " + "  •  ".join(parts))


@click.command("doctor")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--json", "output_json", is_flag=True, default=False, help="Output results as JSON.")
def cmd(project_dir: str | None, output_json: bool) -> None:
    """Check that the environment has everything gr4_modtool needs."""
    cfg = None
    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
    except FileNotFoundError:
        pass

    results = run_doctor(cfg)

    if output_json:
        click.echo(json.dumps([dataclasses.asdict(r) for r in results], indent=2))
    else:
        _print_results(cfg, results)

    if any(r.status == "error" for r in results):
        sys.exit(1)
