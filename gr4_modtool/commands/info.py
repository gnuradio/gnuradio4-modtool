"""info command — list all groups and blocks in the project."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gr4_modtool.project.discovery import discover_groups, load_config


def _block_detail(block_path: Path) -> dict:
    """Return ports and params for a block header; empty lists on parse failure."""
    try:
        from gr4_modtool.commands.add_test import parse_annotated_params, parse_header_info

        text = block_path.read_text()
        info = parse_header_info(block_path)
        params = parse_annotated_params(text)
        return {"ports": {"in": info["in_ports"], "out": info["out_ports"]}, "params": params}
    except Exception:
        return {"ports": {"in": [], "out": []}, "params": []}


@click.command("info")
@click.option(
    "--project-dir", default=None, type=click.Path(exists=True), help="Project root directory."
)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Show ports and parameters per block."
)
@click.option("--catalog", is_flag=True, default=False, help="Print a Markdown block catalog.")
def cmd(project_dir: str | None, output_json: bool, verbose: bool, catalog: bool) -> None:
    """Show all groups and blocks in the project."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)

    if catalog:
        from gr4_modtool.commands.docs import build_catalog

        click.echo(build_catalog(cfg), nl=False)
        return

    if output_json:

        def _block_entry(b):
            entry: dict = {"name": b.name}
            if verbose:
                detail = _block_detail(b.path)
                entry["ports"] = detail["ports"]
                entry["params"] = detail["params"]
            return entry

        data = {
            "name": cfg.name,
            "version": cfg.version,
            "cpp_namespace": cfg.cpp_namespace,
            "build_cmake": cfg.build_cmake,
            "groups": [
                {
                    "name": g.name,
                    "blocks": [_block_entry(b) for b in g.blocks],
                }
                for g in groups
            ],
        }
        click.echo(json.dumps(data, indent=2))
        return

    console = Console()
    console.print(f"\n[bold]Project:[/bold] {cfg.name}  v{cfg.version}")
    console.print(f"[bold]Namespace:[/bold] {cfg.cpp_namespace}")
    console.print(f"[bold]Build:[/bold] cmake={cfg.build_cmake}\n")

    if verbose:
        for group in groups:
            heading = group.name or "(flat)"
            console.print(f"[bold green]{heading}[/bold green]")
            for block in group.blocks:
                detail = _block_detail(block.path)
                lines = [f"[bold]{block.name}[/bold]"]
                in_p = detail["ports"]["in"]
                out_p = detail["ports"]["out"]
                if in_p:
                    lines.append("  in:  " + ", ".join(f"{p['name']}:{p['type']}" for p in in_p))
                if out_p:
                    lines.append("  out: " + ", ".join(f"{p['name']}:{p['type']}" for p in out_p))
                for param in detail["params"]:
                    lines.append(
                        f"  param {param['name']} : {param['type']} — {param['description']}"
                    )
                console.print(Panel("\n".join(lines), expand=False))
        return

    flat = cfg.flat
    title = "Blocks" if flat else "Groups & Blocks"
    table = Table(title=title, show_header=True, header_style="bold cyan")
    if not flat:
        table.add_column("Group", style="green")
    table.add_column("Block", style="white")
    table.add_column("Header", style="dim")

    for group in groups:
        if not group.blocks:
            if flat:
                table.add_row("(no blocks)", "")
            else:
                table.add_row(group.name, "(no blocks)", "")
        else:
            for i, block in enumerate(group.blocks):
                if flat:
                    table.add_row(block.name, str(block.path.name))
                else:
                    table.add_row(group.name if i == 0 else "", block.name, str(block.path.name))

    console.print(table)
