"""show command — display a block's header or test file with syntax highlighting."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary
from rich.console import Console
from rich.syntax import Syntax

from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config


def show_block(
    cfg: ProjectConfig,
    group: str,
    block_name: str,
    show_test: bool = False,
) -> None:
    """Print a block's header (or test file) with C++ syntax highlighting.

    Raises FileNotFoundError if the requested file does not exist.
    """
    if show_test:
        path = cfg.group_test_dir(group) / f"qa_{block_name}.cpp"
    else:
        path = cfg.group_include_dir(group) / f"{block_name}.hpp"

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    Console().print(Syntax(path.read_text(), "cpp", line_numbers=True, theme="monokai"))


@click.command("show")
@click.argument("block_name")
@click.option("--group", default=None, help="Group containing the block.")
@click.option(
    "--test",
    "show_test",
    is_flag=True,
    default=False,
    help="Show the test file instead of the header.",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(block_name: str, group: str | None, show_test: bool, project_dir: str | None) -> None:
    """Display a block's header (or test) with syntax highlighting."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)

    if not groups:
        click.echo("No groups found.", err=True)
        sys.exit(1)

    if cfg.flat:
        group = ""
    elif group is None:
        group = questionary.select("Group:", choices=[g.name for g in groups]).ask()
        if group is None:
            sys.exit(0)

    try:
        show_block(cfg, group, block_name, show_test=show_test)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
