"""test command — run a single block's qa_* test binary without rebuilding."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import click
from rich.console import Console

from gr4_modtool.commands.coverage import (
    coverage_test_env,
    detect_coverage_tool,
    regenerate_coverage_report,
)
from gr4_modtool.commands.lint_headers import lint_header as _lint_header
from gr4_modtool.log import get_logger, log_exit, log_run
from gr4_modtool.project.discovery import find_project_root

log = get_logger(__name__)

try:
    from watchdog.events import FileSystemEventHandler as _FileSystemEventHandler
    from watchdog.observers import Observer as _Observer

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    _Observer = None  # type: ignore[assignment]
    _FileSystemEventHandler = object  # type: ignore[assignment,misc]


def run_block_test(
    project_root: Path,
    build_dir: Path,
    block_name: str,
    *,
    verbose: bool = False,
    extra_env: dict[str, str] | None = None,
) -> int:
    """Run qa_<block_name> inside build_dir using ctest.

    Returns the subprocess exit code.
    extra_env is merged with os.environ when provided (used for coverage profiling).
    """
    cmd = [
        "ctest",
        "--test-dir",
        str(build_dir),
        "-R",
        f"qa_{block_name}",
        "--output-on-failure",
    ]
    if verbose:
        cmd.append("--verbose")

    click.echo(f"  $ {' '.join(cmd)}")
    log_run(log, cmd, build_dir)
    if extra_env:
        log.debug("extra environment: %s", ", ".join(sorted(extra_env)))
    env = {**os.environ, **extra_env} if extra_env else None
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, env=env)
    rc = proc.wait()
    log_exit(log, cmd, rc)
    return rc


def _incremental_build(project_root: Path, build_dir: Path, block_name: str) -> int:
    """Rebuild only qa_<block_name> without a full build."""
    cmd = ["cmake", "--build", str(build_dir), "--target", f"qa_{block_name}"]
    click.echo(f"  $ {' '.join(cmd)}")
    log_run(log, cmd, project_root)
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    rc = proc.wait()
    log_exit(log, cmd, rc)
    return rc


def _find_block_info(project_root: Path, block_name: str) -> tuple[Path, str] | None:
    """Return (hpp_path, group_name) for block_name, or None if not found in config."""
    try:
        from gr4_modtool.project.discovery import discover_groups, load_config

        cfg = load_config(project_root)
        for group in discover_groups(cfg):
            for block in group.blocks:
                if block.name == block_name:
                    return block.path, group.name
    except Exception:
        pass
    return None


def _find_watch_dir(project_root: Path, block_name: str) -> Path:
    """Return the include directory containing block_name.hpp, or blocks/ as fallback."""
    try:
        from gr4_modtool.project.discovery import discover_groups, load_config

        cfg = load_config(project_root)
        for group in discover_groups(cfg):
            for block in group.blocks:
                if block.name == block_name:
                    return cfg.group_include_dir(group.name)
    except Exception:
        pass
    fallback = project_root / "blocks"
    return fallback if fallback.exists() else project_root


def watch_block_test(
    project_root: Path,
    build_dir: Path,
    block_name: str,
    *,
    verbose: bool = False,
    coverage_dir: Path | None = None,
    coverage_output: Path | None = None,
    coverage_tool: str = "auto",
) -> None:
    """Watch block's .hpp for changes, incrementally rebuild and retest on each save.

    When coverage_dir is provided, builds and tests from that directory and
    regenerates the HTML coverage report after each passing test run.
    The coverage_dir must already be configured with coverage flags (run
    `gr4_modtool coverage` once first).
    """
    if not _WATCHDOG_AVAILABLE:
        click.echo("watchdog is required for --watch: pip install watchdog", err=True)
        sys.exit(1)

    # Resolve coverage settings once at startup.
    _active_build = build_dir
    _cov_env: dict[str, str] = {}
    _resolved_tool: str | None = None
    _cov_output: Path | None = None

    if coverage_dir is not None:
        if not coverage_dir.exists():
            click.echo(
                f"Coverage build directory not found: {coverage_dir}\n"
                "Run 'gr4_modtool coverage' once first to configure it.",
                err=True,
            )
            sys.exit(1)
        _resolved_tool = detect_coverage_tool(coverage_tool)
        if _resolved_tool is None:
            click.echo(
                "No coverage tool found. Install gcovr (pip install gcovr) or llvm-cov.",
                err=True,
            )
            sys.exit(1)
        _active_build = coverage_dir
        _cov_output = coverage_output or (project_root / "coverage")
        _cov_env = coverage_test_env(_resolved_tool, _cov_output)

    console = Console()
    last_trigger = -float("inf")
    _block_info = _find_block_info(project_root, block_name)

    def _run_once() -> None:
        nonlocal last_trigger
        now = time.monotonic()
        if now - last_trigger < 1.0:
            return
        last_trigger = now
        console.rule(f"[dim]{time.strftime('%H:%M:%S')} — rebuilding[/dim]")

        if _block_info is not None:
            hpp_path, group_name = _block_info
            issues = _lint_header(hpp_path, group_name)
            if issues:
                for issue in issues:
                    sev_style = "red" if issue.severity == "error" else "yellow"
                    console.print(
                        f"  lint [{sev_style}]{issue.severity}[/{sev_style}]  {issue.issue}"
                    )

        rc = _incremental_build(project_root, _active_build, block_name)
        if rc != 0:
            console.print("[red]Build failed — fix errors and save again[/red]")
            return

        rc_test = run_block_test(
            project_root,
            _active_build,
            block_name,
            verbose=verbose,
            extra_env=_cov_env or None,
        )

        if coverage_dir is not None and rc_test == 0:
            assert _resolved_tool is not None  # validated at startup when coverage_dir is set
            assert _cov_output is not None  # set at startup when coverage_dir is set
            rc_cov = regenerate_coverage_report(
                project_root, _active_build, _resolved_tool, _cov_output
            )
            if rc_cov == 0:
                console.print(f"[dim]Coverage updated → {_cov_output / 'index.html'}[/dim]")

    class _Handler(_FileSystemEventHandler):
        def on_modified(self, event):  # type: ignore[override]
            if not event.is_directory and event.src_path.endswith(".hpp"):
                _run_once()

    watch_dir = _find_watch_dir(project_root, block_name)
    cov_note = f", coverage → {_cov_output}" if coverage_dir else ""
    console.print(f"[dim]Watching {watch_dir} for .hpp changes{cov_note} (Ctrl+C to stop)[/dim]")
    _run_once()

    observer = _Observer()
    observer.schedule(_Handler(), str(watch_dir), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        console.print("\n[dim]Watch stopped.[/dim]")


@click.command("test")
@click.argument("block_name")
@click.option(
    "--build-dir",
    default="build",
    show_default=True,
    help="Build directory (relative to project root).",
)
@click.option("--verbose", "-v", is_flag=True, help="Pass --verbose to ctest.")
@click.option(
    "--watch", "-w", is_flag=True, help="Rebuild and retest on every .hpp save (requires watchdog)."
)
@click.option(
    "--coverage",
    "use_coverage",
    is_flag=True,
    default=False,
    help="Regenerate coverage report after each passing test (--watch only).",
)
@click.option(
    "--coverage-dir",
    default="build-coverage",
    show_default=True,
    help="Pre-configured coverage build directory.",
)
@click.option(
    "--coverage-output",
    default="coverage",
    show_default=True,
    help="Directory for the HTML coverage report.",
)
@click.option(
    "--coverage-tool",
    type=click.Choice(["auto", "gcovr", "llvm-cov"]),
    default="auto",
    show_default=True,
    help="Coverage report tool.",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    block_name: str,
    build_dir: str,
    verbose: bool,
    watch: bool,
    use_coverage: bool,
    coverage_dir: str,
    coverage_output: str,
    coverage_tool: str,
    project_dir: str | None,
) -> None:
    """Run a single block's test binary without rebuilding."""
    if project_dir:
        root = Path(project_dir)
    else:
        root = find_project_root() or Path.cwd()

    bd = (root / build_dir) if not Path(build_dir).is_absolute() else Path(build_dir)

    if use_coverage and not watch:
        click.echo("--coverage requires --watch.", err=True)
        sys.exit(1)

    if watch:
        cov_dir: Path | None = None
        cov_out: Path | None = None
        if use_coverage:
            cov_dir = (
                (root / coverage_dir)
                if not Path(coverage_dir).is_absolute()
                else Path(coverage_dir)
            )
            cov_out = (
                (root / coverage_output)
                if not Path(coverage_output).is_absolute()
                else Path(coverage_output)
            )
        else:
            if not bd.exists():
                click.echo(f"Build directory not found: {bd}", err=True)
                click.echo("Run 'gr4_modtool build' first.", err=True)
                sys.exit(1)
        watch_block_test(
            root,
            bd,
            block_name,
            verbose=verbose,
            coverage_dir=cov_dir,
            coverage_output=cov_out,
            coverage_tool=coverage_tool,
        )
    else:
        if not bd.exists():
            click.echo(f"Build directory not found: {bd}", err=True)
            click.echo("Run 'gr4_modtool build' first.", err=True)
            sys.exit(1)
        rc = run_block_test(root, bd, block_name, verbose=verbose)
        sys.exit(rc)
