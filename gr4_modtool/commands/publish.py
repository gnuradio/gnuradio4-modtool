"""publish command — pre-flight release checks and stub publish dispatch."""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table

from gr4_modtool.commands.validate import validate_project
from gr4_modtool.commands.version_bump import _parse_semver
from gr4_modtool.log import get_logger, log_run
from gr4_modtool.project.discovery import ProjectConfig, load_config

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

KNOWN_TARGETS: dict[str, str] = {
    "local": "Pre-flight checks only (stub)",
    "github": "GitHub Release via gh CLI (stub)",
}

_CMAKE_VERSION_RE = re.compile(r"project\([^)]*\bVERSION\s+([\d.]+)", re.DOTALL)


@dataclass
class PreFlightResult:
    check_id: str  # "version" | "validate" | "cmake_sync" | "git_clean" | "git_tag"
    status: str  # "pass" | "warn" | "fail" | "skip"
    detail: str


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_version(cfg: ProjectConfig) -> PreFlightResult:
    try:
        _parse_semver(cfg.version)
        return PreFlightResult("version", "pass", cfg.version)
    except ValueError:
        return PreFlightResult("version", "fail", f"'{cfg.version}' is not in X.Y.Z format")


def _check_validate(cfg: ProjectConfig) -> PreFlightResult:
    issues = validate_project(cfg)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        return PreFlightResult(
            "validate", "fail", f"{len(errors)} error(s) found — run 'validate' for details"
        )
    warnings = [i for i in issues if i.severity == "warning"]
    if warnings:
        return PreFlightResult("validate", "warn", f"0 errors, {len(warnings)} warning(s)")
    return PreFlightResult("validate", "pass", "no issues")


def _check_cmake_sync(cfg: ProjectConfig) -> PreFlightResult:
    cmake = cfg.root / "CMakeLists.txt"
    if not cmake.exists():
        return PreFlightResult("cmake_sync", "skip", "CMakeLists.txt not present")
    m = _CMAKE_VERSION_RE.search(cmake.read_text())
    if not m:
        return PreFlightResult("cmake_sync", "skip", "no VERSION in CMakeLists.txt")
    if m.group(1) != cfg.version:
        return PreFlightResult(
            "cmake_sync",
            "warn",
            f"CMakeLists.txt VERSION '{m.group(1)}' ≠ config '{cfg.version}'",
        )
    return PreFlightResult("cmake_sync", "pass", "matches config")


def _git_run(args: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    cmd = ["git"] + args
    log_run(log, cmd, cwd)
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except FileNotFoundError:
        log.warning("git not found on PATH; skipping '%s'", " ".join(args))
        return None


def _check_git_clean(cfg: ProjectConfig) -> PreFlightResult:
    result = _git_run(["status", "--porcelain"], cfg.root)
    if result is None or result.returncode != 0:
        return PreFlightResult("git_clean", "skip", "git unavailable or not a git repo")
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        return PreFlightResult("git_clean", "warn", f"{len(dirty)} uncommitted file(s)")
    return PreFlightResult("git_clean", "pass", "working tree clean")


def _check_git_tag(cfg: ProjectConfig) -> PreFlightResult:
    tag = f"v{cfg.version}"
    result = _git_run(["tag", "--list", tag], cfg.root)
    if result is None or result.returncode != 0:
        return PreFlightResult("git_tag", "skip", "git unavailable or not a git repo")
    if result.stdout.strip():
        return PreFlightResult("git_tag", "warn", f"tag '{tag}' already exists")
    return PreFlightResult("git_tag", "pass", f"tag '{tag}' not yet created")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def pre_flight(cfg: ProjectConfig) -> list[PreFlightResult]:
    """Run all pre-flight checks and return results (never short-circuits)."""
    return [
        _check_version(cfg),
        _check_validate(cfg),
        _check_cmake_sync(cfg),
        _check_git_clean(cfg),
        _check_git_tag(cfg),
    ]


# ---------------------------------------------------------------------------
# Stub publisher
# ---------------------------------------------------------------------------


def _do_publish(cfg: ProjectConfig, target: str) -> None:
    if target == "github":
        click.echo(f"  [stub] would create GitHub release for v{cfg.version}")
        click.echo(f"  [stub] gh release create v{cfg.version} --generate-notes")
    else:
        click.echo(
            f"  [stub] target '{target}' has no publish implementation yet — "
            "add it to commands/publish.py"
        )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

_STATUS_STYLE = {
    "pass": "[green]✓ pass[/green]",
    "warn": "[yellow]⚠ warn[/yellow]",
    "fail": "[red]✗ fail[/red]",
    "skip": "[dim]– skip[/dim]",
}


def _render_table(results: list[PreFlightResult], console: Console | None = None) -> None:
    if console is None:
        console = Console()

    tbl = Table(
        title="Pre-flight Checks",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold cyan",
    )
    tbl.add_column("Check", style="white")
    tbl.add_column("Status", justify="center")
    tbl.add_column("Detail", style="dim")

    for r in results:
        tbl.add_row(r.check_id, _STATUS_STYLE.get(r.status, r.status), r.detail)

    console.print(tbl)

    failures = [r for r in results if r.status == "fail"]
    if failures:
        console.print(f"[red]✗  {len(failures)} check(s) failed — resolve before publishing[/red]")
    else:
        console.print("[green]✓  Ready to publish[/green]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("publish")
@click.option(
    "--target",
    default="local",
    type=click.Choice(list(KNOWN_TARGETS), case_sensitive=False),
    show_default=True,
    help="Publish destination.",
)
@click.option("--dry-run", "-n", is_flag=True, help="Pre-flight only, no publish step.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.option("--json", "output_json", is_flag=True, help="Machine-readable pre-flight output.")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    target: str,
    dry_run: bool,
    yes: bool,
    output_json: bool,
    project_dir: str | None,
) -> None:
    """Check release readiness and publish the module (stub)."""
    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    results = pre_flight(cfg)

    if output_json:
        failures = [r for r in results if r.status == "fail"]
        data = {
            "results": [dataclasses.asdict(r) for r in results],
            "pass_count": sum(1 for r in results if r.status == "pass"),
            "warn_count": sum(1 for r in results if r.status == "warn"),
            "fail_count": len(failures),
            "skip_count": sum(1 for r in results if r.status == "skip"),
            "ready": len(failures) == 0,
        }
        click.echo(json.dumps(data, indent=2))
        if failures:
            sys.exit(1)
        return

    _render_table(results)

    if any(r.status == "fail" for r in results):
        sys.exit(1)

    if dry_run:
        click.echo("(dry-run — skipping publish step)")
        return

    if not yes:
        try:
            import questionary  # type: ignore[import-untyped]

            if not questionary.confirm("Proceed with publish?", default=True).ask():
                click.echo("Aborted.")
                return
        except ImportError:
            pass

    _do_publish(cfg, target)
