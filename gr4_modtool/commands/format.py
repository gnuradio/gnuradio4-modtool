"""format command — run clang-format over project headers and test sources."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click

from gr4_modtool.log import get_logger, log_exit, log_run
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config

log = get_logger(__name__)


def _collect_files(cfg: ProjectConfig, group_names: list[str] | None) -> list[Path]:
    """Return all .hpp and .cpp files for the selected groups."""
    all_groups = discover_groups(cfg)
    files: list[Path] = []
    for g in all_groups:
        if group_names is not None and g.name not in group_names:
            continue
        inc = cfg.group_include_dir(g.name)
        tst = cfg.group_test_dir(g.name)
        if inc.exists():
            files.extend(inc.glob("*.hpp"))
        if tst.exists():
            files.extend(tst.glob("*.cpp"))
    return files


def format_files(
    cfg: ProjectConfig,
    groups: list[str] | None = None,
    *,
    check_only: bool = False,
    style: str | None = None,
) -> int:
    """Run clang-format over all headers and test sources for the given groups.

    Returns 0 on success.  In check_only mode returns non-zero if any file
    needs formatting.  Returns 0 (with a warning) if clang-format is not installed.
    """
    if shutil.which("clang-format") is None:
        click.echo("Warning: clang-format not found — skipping format.", err=True)
        return 0

    files = _collect_files(cfg, groups)
    if not files:
        click.echo("No files to format.")
        return 0

    cmd: list[str] = ["clang-format"]
    if check_only:
        cmd += ["--dry-run", "--Werror"]
    else:
        cmd.append("-i")
    if style:
        cmd.append(f"-style={style}")
    cmd.extend(str(f) for f in files)

    log_run(log, cmd)
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    rc = proc.wait()
    log_exit(log, cmd, rc)
    return rc


@click.command("format")
@click.option("--group", default=None, help="Format only this group.")
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help="Dry-run; exit 1 if any file needs formatting (for CI).",
)
@click.option("--style", default=None, help="clang-format style: file, llvm, google, chromium, …")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    group: str | None,
    check_only: bool,
    style: str | None,
    project_dir: str | None,
) -> None:
    """Run clang-format over block headers and test sources."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    group_filter = [group] if group else None
    rc = format_files(cfg, groups=group_filter, check_only=check_only, style=style)
    sys.exit(rc)
