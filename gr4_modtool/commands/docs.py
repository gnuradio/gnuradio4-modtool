"""docs command — write Doxyfile and/or print a Markdown block catalog."""

from __future__ import annotations

from pathlib import Path

import click

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config
from gr4_modtool.templates import render


def write_doxyfile(cfg: ProjectConfig) -> list[Path]:
    ctx = {
        "project_name": cfg.name,
        "version": cfg.version,
        "gr4_include_prefix": cfg.gr4_include_prefix,
    }
    path = cfg.root / "Doxyfile"
    write_text(path, render("Doxyfile.j2", ctx, cfg.root))
    return [path]


def build_catalog(cfg: ProjectConfig) -> str:
    from gr4_modtool.commands.add_test import parse_annotated_params, parse_header_info

    groups = discover_groups(cfg)
    lines = [
        f"# Block Catalog — {cfg.name}",
        "",
        "| Group | Block | Ports In | Ports Out | Style | Parameters |",
        "|---|---|---|---|---|---|",
    ]
    for g in groups:
        for b in g.blocks:
            try:
                info = parse_header_info(b.path)
                params = parse_annotated_params(b.path.read_text())
            except Exception:
                info = {"in_ports": [], "out_ports": [], "processing_style": "?"}
                params = []

            in_str = ", ".join(f"{p['name']}:{p['type']}" for p in info["in_ports"]) or "—"
            out_str = ", ".join(f"{p['name']}:{p['type']}" for p in info["out_ports"]) or "—"
            param_str = ", ".join(f"{p['name']}:{p['type']}" for p in params) or "—"
            lines.append(
                f"| {g.name} | {b.name} | {in_str} | {out_str} "
                f"| {info['processing_style']} | {param_str} |"
            )

    return "\n".join(lines) + "\n"


@click.command("docs")
@click.option(
    "--catalog",
    is_flag=True,
    default=False,
    help="Print a Markdown block catalog instead of writing a Doxyfile.",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Write catalog output to this file (default: stdout).",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(catalog: bool, output: str | None, project_dir: str | None) -> None:
    """Write a Doxyfile for the project, or print a Markdown block catalog."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if catalog:
        text = build_catalog(cfg)
        if output:
            write_text(Path(output), text)
            click.echo(f"Written: {output}")
        else:
            click.echo(text, nl=False)
        return

    written = write_doxyfile(cfg)
    click.echo("Written:")
    for p in written:
        click.echo(f"  {p}")
    click.echo("\nRun 'doxygen Doxyfile' to generate HTML docs in docs/html/")
