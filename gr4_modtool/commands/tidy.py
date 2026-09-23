"""tidy command — run clang-tidy on project block headers."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click

from gr4_modtool.fileops import write_text
from gr4_modtool.log import get_logger, log_exit, log_run
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config
from gr4_modtool.templates import render

log = get_logger(__name__)


def write_clang_config(cfg: ProjectConfig) -> list[Path]:
    """Write .clang-format and .clang-tidy at the project root. Returns created paths."""
    ctx = {
        "project_name": cfg.name,
        "gr4_include_prefix": cfg.gr4_include_prefix,
    }
    clang_format = cfg.root / ".clang-format"
    clang_tidy = cfg.root / ".clang-tidy"
    write_text(clang_format, render("clang-format.j2", ctx, cfg.root))
    write_text(clang_tidy, render("clang-tidy.j2", ctx, cfg.root))
    return [clang_format, clang_tidy]


def write_ci_clang(cfg: ProjectConfig) -> list[Path]:
    """Write .github/workflows/clang-ci.yml for the OOT project."""
    ctx = {"project_name": cfg.name}
    ci_dir = cfg.root / ".github" / "workflows"
    ci_dir.mkdir(parents=True, exist_ok=True)
    path = ci_dir / "clang-ci.yml"
    write_text(path, render("ci_clang.yml.j2", ctx, cfg.root))
    return [path]


def run_tidy(
    cfg: ProjectConfig,
    build_dir: Path,
    groups: list[str] | None = None,
    *,
    fix: bool = False,
) -> int:
    """Run clang-tidy on block headers. Returns subprocess exit code."""
    if shutil.which("clang-tidy") is None:
        click.echo("Warning: clang-tidy not found — skipping.", err=True)
        return 0

    compile_commands = build_dir / "compile_commands.json"
    if not compile_commands.exists():
        click.echo(
            f"compile_commands.json not found in {build_dir}.\n"
            "Configure first: gr4_modtool build  "
            "or: cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -B build",
            err=True,
        )
        return 1

    all_groups = discover_groups(cfg)
    selected = {g.name for g in all_groups} if groups is None else set(groups)

    files: list[Path] = []
    for group in all_groups:
        if group.name in selected:
            files.extend(sorted(cfg.group_include_dir(group.name).glob("*.hpp")))

    if not files:
        click.echo("No header files found.")
        return 0

    cmd = ["clang-tidy", "-p", str(build_dir)]
    if fix:
        cmd.append("--fix")
    cmd.extend(str(f) for f in files)

    n = len(files)
    click.echo(f"  $ clang-tidy -p {build_dir} … ({n} file{'s' if n != 1 else ''})")
    log_run(log, cmd)
    rc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr).wait()
    log_exit(log, cmd, rc)
    return rc


@click.command("tidy")
@click.option(
    "--build-dir",
    default="build",
    show_default=True,
    help="Build directory containing compile_commands.json.",
)
@click.option("--group", default=None, help="Lint only this group.")
@click.option("--fix", is_flag=True, default=False, help="Apply clang-tidy fixes in place.")
@click.option(
    "--init",
    "do_init",
    is_flag=True,
    default=False,
    help="Generate .clang-format and .clang-tidy config files and exit.",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    build_dir: str,
    group: str | None,
    fix: bool,
    do_init: bool,
    project_dir: str | None,
) -> None:
    """Run clang-tidy on block headers (requires a cmake build with compile_commands.json).

    Use --init to generate .clang-format / .clang-tidy config files for an existing project.
    """
    cfg = load_config(Path(project_dir) if project_dir else None)

    if do_init:
        written = write_clang_config(cfg)
        click.echo("Created:")
        for p in written:
            click.echo(f"  {p}")
        return

    root = cfg.root
    bd = Path(build_dir) if Path(build_dir).is_absolute() else root / build_dir
    rc = run_tidy(cfg, bd, [group] if group else None, fix=fix)
    if rc != 0:
        sys.exit(rc)
