"""report command — print a block-count summary for the current project.

This module demonstrates the minimum structure for a gr4_modtool command plugin:

  1. Define a Click command decorated with @click.command().
  2. Include --project-dir so the command can be run from any directory.
  3. Use load_config / discover_groups from gr4_modtool.project.discovery to
     access the project state.
  4. Handle FileNotFoundError when no .gr4modtool.toml is found.

The entry point in pyproject.toml points at the `cmd` object in this module:

    [project.entry-points."gr4_modtool.commands"]
    report = "gr4_modtool_example_plugin.commands.report:cmd"
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from gr4_modtool.project.discovery import discover_groups, load_config


@click.command("report")
@click.option(
    "--project-dir",
    default=None,
    type=click.Path(exists=True),
    help="Project root (default: current directory).",
)
@click.option(
    "--json", "output_json", is_flag=True, help="Emit machine-readable JSON instead of a table."
)
def cmd(project_dir: str | None, output_json: bool) -> None:
    """Print a block-count summary for the project.

    Lists every group with its block count and the total for the whole
    project.  Use --json for machine-readable output.

    Example
    -------
    $ gr4_modtool report

        Group    Blocks
        -------  ------
        dsp           3
        io            1
        -------  ------
        TOTAL         4
    """
    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    groups = discover_groups(cfg)

    if output_json:
        import json

        data = {
            "project": cfg.name,
            "version": cfg.version,
            "groups": [{"name": g.name or "(flat)", "block_count": len(g.blocks)} for g in groups],
            "total_blocks": sum(len(g.blocks) for g in groups),
        }
        click.echo(json.dumps(data, indent=2))
        return

    # Plain text table
    col_w = max((len(g.name or "(flat)") for g in groups), default=5)
    col_w = max(col_w, 5)
    divider = f"  {'─' * col_w}  {'─' * 6}"

    click.echo(f"\n  {'Group':<{col_w}}  Blocks")
    click.echo(divider)

    total = 0
    for group in groups:
        name = group.name or "(flat)"
        count = len(group.blocks)
        total += count
        click.echo(f"  {name:<{col_w}}  {count:>6}")

    click.echo(divider)
    click.echo(f"  {'TOTAL':<{col_w}}  {total:>6}\n")
